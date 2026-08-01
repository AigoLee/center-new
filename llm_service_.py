"""
LLM 调用服务: 意图识别 + 回答生成 + 纪要生成
"""
import json
from openai import OpenAI
from config import LLM_KEY, LLM_URL, LLM_MODEL, MAX_FOLLOWUP

_client = None
_demo = not LLM_KEY


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=LLM_KEY, base_url=LLM_URL)
    return _client


def is_demo():
    return _demo


# ==================== 意图识别 ====================

INTENT_P = """你是基层问题解决中心智能助手。分析用户问题,返回JSON。

类别: 咨询/投诉/建议/报修/求助/其他
紧急度: 普通/紧急/特急

JSON格式:
{
    "is_clear": true,
    "follow_up": "追问问题或null",
    "data": {
        "category": "类别",
        "intent": "用户意图(一句话)",
        "urgency": "普通",
        "department": "部门或null",
        "keywords": ["k1","k2"],
        "refined": "补全后问题描述",
        "context": "补充上下文或null"
    }
}
追问简短,最多2轮,一次只问1-2个关键信息。"""


def analyze(question, history=None, round_num=0):
    """意图识别, 返回 (is_clear, follow_up, data)"""
    if is_demo():
        return _demo_analyze(question)

    ctx = ""
    if history:
        ctx = "历史:\n" + "\n".join(
            [f"问:{h['q']}\n答:{h['a']}" for h in history]
        ) + "\n"

    msg = f"{ctx}用户: {question}"
    if round_num >= MAX_FOLLOWUP:
        msg += "\n(已达追问上限,直接输出结构化描述)"

    try:
        r = client().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": INTENT_P},
                      {"role": "user", "content": msg}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        print("### LLM raw: " + r)
        d = json.loads(r.choices[0].message.content)
        print("### LLM Res: " + d)
        clear = d.get("is_clear", True) or round_num >= MAX_FOLLOWUP
        fu = d.get("follow_up") if not clear else None
        return clear, fu, d.get("data") if clear else None
    except Exception as e:
        print(f"[analyze] LLM异常, 降级处理: {e}")
        # 降级: 如果问题太短, 追问一下
        if len(question) < 8:
            return False, "请详细描述你的问题, 例如涉及什么业务、遇到什么困难?", None
        return True, None, {"category": "其他", "intent": "未识别",
                            "urgency": "普通", "department": None,
                            "keywords": [], "refined": question, "context": None}


# 演示模式: 简单关键词匹配
_DEMO_KW = {
    "工资": ("投诉", "薪资核查"),
    "绩效": ("投诉", "绩效核查"),
    "报销": ("咨询", "报销流程"),
    "出差": ("咨询", "差旅报销"),
    "医保": ("咨询", "医疗保险"),
    "年假": ("咨询", "年假政策"),
    "加班": ("咨询", "加班政策"),
    "调岗": ("咨询", "岗位调动"),
    "打印机": ("报修", "设备维修"),
    "维修": ("报修", "设备故障"),
    "密码": ("求助", "账号登录"),
    "登录": ("求助", "系统登录"),
    "食堂": ("投诉", "餐饮反馈"),
    "笔记本": ("咨询", "设备申领"),
    "入职": ("咨询", "入职流程"),
    "离职": ("咨询", "离职手续"),
}


def _demo_analyze(question):
    import re
    cat, intent = "其他", "未识别"
    for kw, (c, i) in _DEMO_KW.items():
        if kw in question:
            cat, intent = c, i
            break
    kws = list(set(re.findall(r'[\u4e00-\u9fa5]{2,6}', question)[:3]))
    # 演示模式追问: 问题太短或太模糊
    if len(question) < 6:
        return False, "请详细描述你的问题, 例如涉及什么业务?", None
    if cat == "其他":
        return False, "请问你遇到的是什么类型的问题? 例如: 工资、报销、请假、设备报修等", None
    return True, None, {"category": cat, "intent": intent,
                        "urgency": "普通", "department": None,
                        "keywords": kws, "refined": question, "context": None}


# ==================== 回答生成 ====================

GEN_P = """你是基层问题解决中心AI助手。基于参考资料回答问题。

要求: 准确、专业、简洁。有依据则引用说明。资料不足如实说明。

参考资料:
{refs}

问题 [{category}|{intent}]: {question}
"""


def generate_answer(structured, refs_text=""):
    """基于材料生成回答"""
    if is_demo():
        if refs_text:
            return f"[演示模式] 根据材料库匹配:\n\n{refs_text[:1000]}\n\n---\n请配置 DEEPSEEK_API_KEY 启用完整AI能力。"
        return "[演示模式] 未找到匹配,请配置 API Key。"

    prompt = GEN_P.format(
        refs=refs_text or "无可参考资料",
        category=structured.get("category", ""),
        intent=structured.get("intent", ""),
        question=structured.get("refined", "")
    )
    try:
        r = client().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=2000
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"生成失败: {e}"


# ==================== 纪要生成 ====================

SUM_P = """基于以下信息生成解决纪要。输出JSON:

问题: {q}
类别: {cat} | 意图: {intent}
回答: {a}
来源: {src}

JSON: {{"summary":"纪要全文","kb_q":"知识库问题摘要","kb_a":"知识库答案(200字)","score":0.85}}"""


def generate_summary(question, category, intent, answer, source):
    if is_demo():
        return {"summary": f"[演示] {question[:100]}\n{answer[:200]}",
                "kb_q": question[:100], "kb_a": answer[:200], "score": 0.7}

    try:
        r = client().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": SUM_P.format(
                q=question[:500], cat=category, intent=intent,
                a=answer[:2000], src=source)}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(r.choices[0].message.content)
    except Exception:
        return {"summary": f"{question[:100]}\n{answer[:200]}",
                "kb_q": question[:100], "kb_a": answer[:200], "score": 0.5}
