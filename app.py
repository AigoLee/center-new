"""
Flask 主应用 — 基层问题解决中心
"""
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

from config import HOST, PORT, HISTORY_KB, MATERIAL_KB, HIGH_SIM, MEDIUM_SIM, TOP_K
from models import init_db, get_db, Question, Review
from kb_service import kb
from llm_service import analyze, generate_answer, generate_summary, is_demo

app = Flask(__name__, static_folder="static", static_url_path="")
init_db()

# ==================== 首页 ====================
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ==================== 用户端 ====================

@app.route("/api/ask", methods=["POST"])
def ask():
    """提交问题"""
    d = request.json
    q = d.get("question", "").strip()
    sid = d.get("session_id") or str(uuid.uuid4())
    if not q:
        return jsonify({"error": "问题不能为空"}), 400

    db = get_db()
    # 查找会话中的进行中问题
    prev = db.query(Question).filter(
        Question.session_id == sid,
        Question.status.in_(["收集中", "匹配中"])
    ).order_by(Question.created_at.desc()).first()

    fh = list(prev.followup_history) if prev else []   # copy 避免副作用
    rn = prev.followup_round if prev else 0

    # ---- 把当前输入填入上一轮追问(提前,让LLM知道上下文) ----
    if prev and prev.status == "收集中" and fh:
        fh[-1]["a"] = q

    # 意图识别
    clear, follow_up, data = analyze(q, fh, rn)

    # ---- 不清晰 → 追问 ----
    if not clear and follow_up:
        new_fh = fh + [{"q": follow_up, "a": ""}]
        rec = Question(
            session_id=sid, original=q, status="收集中",
            followup_round=rn + 1,
            followup_history=new_fh
        )
        db.add(rec); db.commit(); rid = rec.id; db.close()
        return jsonify({"question_id": rid, "session_id": sid, "status": "收集中",
                        "message": "请补充信息:", "follow_up": follow_up})

    # ---- 持久化更新追问历史到DB ----
    if prev and prev.status == "收集中":
        prev.followup_history = fh
        prev.followup_round = rn

    # ---- 创建/更新记录 ----
    if prev:
        rec = prev; rec.original = q
    else:
        rec = Question(session_id=sid, original=q); db.add(rec)

    rec.refined = data.get("refined", q)
    rec.category = data.get("category", "其他")
    rec.intent = data.get("intent", "未识别")
    rec.urgency = data.get("urgency", "普通")
    rec.department = data.get("department")
    rec.keywords = data.get("keywords", [])
    rec.status = "匹配中"
    db.commit()

    # ========== 双路RAG ==========
    query = data.get("refined", q)
    if data.get("keywords"):
        query += " " + " ".join(data["keywords"])

    # 步骤1: 历史知识库
    hist = kb.search(HISTORY_KB, query, TOP_K)

    if hist:
        best = hist[0]
        sim = best["similarity"]

        if sim >= HIGH_SIM:
            refs = "\n".join([f"[{i+1}] {r['metadata'].get('title','')}({r['similarity']:.2f})"
                              for i, r in enumerate(hist[:3])])
            answer = f"📚 根据历史记录找到解答:\n\n{best['document']}\n\n引用:\n{refs}"
            source = "history_kb"
        elif sim >= MEDIUM_SIM:
            refs = "\n".join([f"[{i+1}] {r['metadata'].get('title','')}({r['similarity']:.2f})"
                              for i, r in enumerate(hist[:3])])
            answer = f"📚 可能相关的历史记录:\n\n{best['document']}\n\n{refs}\n\n如未解决请点「未解决」。"
            source = "history_kb"
        else:
            hist = []  # 低于阈值,走材料库
            answer = None
            source = None
    else:
        answer = None
        source = None

    # 步骤2: 材料知识库 + LLM
    if answer is None:
        mat = kb.search(MATERIAL_KB, query, TOP_K)
        refs_text = ""
        if mat:
            refs_text = "\n\n".join([
                f"### 参考{i+1}: {r['metadata'].get('title','')}\n{r['document']}"
                for i, r in enumerate(mat)
            ])
        answer = generate_answer(data, refs_text)
        source = "material_kb" if mat else "llm_generated"
        references = mat
    else:
        references = hist[:3]

    rec.answer = answer
    rec.answer_source = source
    rec.references = json.dumps(references[:5], ensure_ascii=False)
    rec.status = "已回答"
    db.commit()
    rid = rec.id
    db.close()

    return jsonify({
        "question_id": rid, "session_id": sid, "status": "已回答",
        "structured": {"category": rec.category, "intent": rec.intent,
                       "urgency": rec.urgency, "department": rec.department,
                       "keywords": rec.keywords, "refined": rec.refined},
        "message": answer, "source": source, "references": references[:5]
    })


@app.route("/api/feedback", methods=["POST"])
def feedback():
    """用户反馈"""
    d = request.json
    qid = d.get("question_id")
    resolved = d.get("resolved", False)
    sat = d.get("satisfaction")

    db = get_db()
    rec = db.query(Question).filter(Question.id == qid).first()
    if not rec:
        db.close(); return jsonify({"error": "不存在"}), 404

    rec.resolved = resolved; rec.satisfaction = sat

    if resolved:
        source = rec.answer_source or ""
        # 只有材料KB/AI生成的新回答才需要审核入库,历史KB直接命中不需要
        if source in ("material_kb", "llm_generated"):
            try:
                s = generate_summary(rec.original, rec.category or "其他",
                                     rec.intent or "未识别", rec.answer or "", source)
                rv = Review(question_id=rec.id, original_question=rec.original,
                            answer=rec.answer or "", summary=s.get("summary", ""),
                            source=source, satisfaction=sat)
                db.add(rv); db.flush()
                rec.review_id = rv.id; rec.status = "待审核"
                msg = "感谢反馈! 纪要已生成,待管理员审核后入库。"
            except Exception as e:
                rec.status = "已解决"
                msg = f"已记录。(纪要生成失败:{e})"
        else:
            # 历史KB命中,直接标记已解决
            rec.status = "已解决"
            msg = "感谢反馈! 问题已解决。"
    else:
        rec.status = "未解决"
        msg = "已记录,管理员将跟进。"

    final_status = rec.status
    db.commit()
    db.close()
    return jsonify({"status": final_status, "message": msg})


# ==================== 管理员端 ====================

@app.route("/api/admin/dashboard")
def dashboard():
    db = get_db()
    total = db.query(Question).count()
    resolved = db.query(Question).filter(Question.resolved == True).count()
    unresolved = db.query(Question).filter(Question.status == "未解决").count()
    pending = db.query(Review).filter(Review.status == "pending").count()

    from sqlalchemy import func
    cats = db.query(Question.category, func.count(Question.id)).group_by(Question.category).all()
    recent = db.query(Question).filter(Question.status == "未解决").order_by(
        Question.created_at.desc()).limit(10).all()
    db.close()

    rate = round(resolved / total * 100, 1) if total > 0 else 0
    return jsonify({
        "total": total, "resolved": resolved, "unresolved": unresolved,
        "pending_review": pending, "rate": rate,
        "history_kb": kb.count(HISTORY_KB), "material_kb": kb.count(MATERIAL_KB),
        "categories": [{"name": c, "count": cnt} for c, cnt in cats if c],
        "recent_unresolved": [{"id": r.id, "q": r.original[:80],
                               "cat": r.category, "time": r.created_at.isoformat()}
                              for r in recent]
    })


@app.route("/api/admin/reviews")
def reviews():
    status = request.args.get("status", "pending")
    db = get_db()
    q = db.query(Review)
    if status != "all":
        q = q.filter(Review.status == status)
    records = q.order_by(Review.created_at.desc()).limit(50).all()
    db.close()
    return jsonify({"records": [{
        "id": r.id, "question_id": r.question_id,
        "q": r.original_question, "a": r.answer,
        "summary": r.summary, "edited": r.edited_summary,
        "source": r.source, "sat": r.satisfaction,
        "status": r.status, "notes": r.admin_notes,
        "kb_id": r.kb_entry_id,
        "created": r.created_at.isoformat() if r.created_at else None
    } for r in records]})


@app.route("/api/admin/reviews/<rid>/approve", methods=["POST"])
def approve(rid):
    d = request.json or {}
    db = get_db()
    rv = db.query(Review).filter(Review.id == rid).first()
    if not rv:
        db.close(); return jsonify({"error": "不存在"}), 404

    # 提取问答对入库
    edited = d.get("edited_summary") or rv.summary
    kb_q = rv.original_question[:100]
    kb_a = edited
    text = f"问题: {kb_q}\n回答: {kb_a}"

    # 查找原始问题获取分类
    q = db.query(Question).filter(Question.id == rv.question_id).first()
    meta = {
        "title": kb_q, "question": kb_q, "answer": kb_a,
        "category": q.category if q else "咨询",
        "department": q.department if q else "",
        "type": "qa_pair", "question_id": rv.question_id,
        "indexed_at": datetime.now().isoformat()
    }
    kb_id = kb.add(HISTORY_KB, text, meta, f"qa_{rv.question_id}")

    rv.status = "approved"; rv.admin_notes = d.get("notes", "")
    rv.edited_summary = edited; rv.kb_entry_id = kb_id
    rv.reviewed_at = datetime.now()
    if q:
        q.status = "已入库"
    db.commit(); db.close()
    return jsonify({"ok": True, "kb_id": kb_id})


@app.route("/api/admin/reviews/<rid>/reject", methods=["POST"])
def reject(rid):
    d = request.json or {}
    db = get_db()
    rv = db.query(Review).filter(Review.id == rid).first()
    if not rv:
        db.close(); return jsonify({"error": "不存在"}), 404
    rv.status = "rejected"; rv.admin_notes = d.get("notes", "")
    rv.reviewed_at = datetime.now()
    q = db.query(Question).filter(Question.id == rv.question_id).first()
    if q:
        q.status = "已驳回"
    db.commit(); db.close()
    return jsonify({"ok": True})


@app.route("/api/admin/unresolved")
def unresolved():
    db = get_db()
    records = db.query(Question).filter(
        Question.status == "未解决"
    ).order_by(Question.created_at.desc()).limit(50).all()
    db.close()
    return jsonify({"records": [{
        "id": r.id, "q": r.original, "refined": r.refined,
        "category": r.category, "intent": r.intent,
        "answer": r.answer, "source": r.answer_source,
        "time": r.created_at.isoformat() if r.created_at else None
    } for r in records]})


# ==================== 知识库维护 ====================

@app.route("/api/admin/kb/<kb_name>")
def kb_list(kb_name):
    if kb_name not in (HISTORY_KB, MATERIAL_KB):
        return jsonify({"error": "无效"}), 400
    off = int(request.args.get("offset", 0))
    lim = int(request.args.get("limit", 50))
    entries = kb.list_entries(kb_name, off, lim)
    return jsonify({"kb": kb_name, "total": kb.count(kb_name), "entries": entries})


@app.route("/api/admin/kb/<kb_name>/add", methods=["POST"])
def kb_add(kb_name):
    if kb_name not in (HISTORY_KB, MATERIAL_KB):
        return jsonify({"error": "无效"}), 400
    d = request.json
    if kb_name == HISTORY_KB:
        if not d.get("question"):
            return jsonify({"error": "需要question"}), 400
        text = f"问题: {d['question']}\n回答: {d.get('answer','')}"
        meta = {"title": d["question"][:100], "question": d["question"],
                "answer": d.get("answer", ""), "category": d.get("category", "咨询"),
                "department": d.get("department", ""),
                "tags": ",".join(d.get("tags", []))}
    else:
        if not d.get("content"):
            return jsonify({"error": "需要content"}), 400
        text = d["content"]
        meta = {"title": d.get("title", ""), "source": d.get("source", ""),
                "category": d.get("category", ""),
                "tags": ",".join(d.get("tags", []))}
    eid = kb.add(kb_name, text, meta)
    return jsonify({"ok": True, "id": eid})


@app.route("/api/admin/kb/<kb_name>/<eid>", methods=["DELETE"])
def kb_delete(kb_name, eid):
    if kb_name not in (HISTORY_KB, MATERIAL_KB):
        return jsonify({"error": "无效"}), 400
    kb.delete(kb_name, eid)
    return jsonify({"ok": True})


@app.route("/api/admin/kb/<kb_name>/<eid>", methods=["PUT"])
def kb_update(kb_name, eid):
    """编辑知识库条目"""
    if kb_name not in (HISTORY_KB, MATERIAL_KB):
        return jsonify({"error": "无效"}), 400
    d = request.json
    if kb_name == HISTORY_KB:
        q = d.get("question", "")
        a = d.get("answer", "")
        if not q and not a:
            return jsonify({"error": "无更新内容"}), 400
        text = f"问题: {q}\n回答: {a}"
        meta = {"title": q[:100], "question": q, "answer": a,
                "category": d.get("category", "咨询"),
                "department": d.get("department", ""),
                "tags": ",".join(d.get("tags", []))}
    else:
        content = d.get("content", "")
        if not content:
            return jsonify({"error": "无更新内容"}), 400
        text = content
        meta = {"title": d.get("title", ""), "source": d.get("source", ""),
                "category": d.get("category", ""),
                "tags": ",".join(d.get("tags", []))}
    kb.update(kb_name, eid, text, meta)
    return jsonify({"ok": True})


# ==================== 启动 ====================
if __name__ == "__main__":
    print("=" * 50)
    print("  基层问题解决中心 v2.0")
    print(f"  演示模式: {'是' if is_demo() else '否 (LLM已连接)'}")
    print(f"  历史KB: {kb.count(HISTORY_KB)}条 | 材料KB: {kb.count(MATERIAL_KB)}条")
    print(f"  地址: http://localhost:{PORT}")
    print("=" * 50)
    app.run(host=HOST, port=PORT, debug=True)
