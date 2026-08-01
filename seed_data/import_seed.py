"""种子数据导入脚本"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from kb_service import kb
from config import HISTORY_KB, MATERIAL_KB

def import_history():
    f = Path(__file__).parent / "history_qa.json"
    if not f.exists(): return print(f"  {f} 不存在")
    data = json.loads(f.read_text(encoding="utf-8"))
    print(f"  导入 {len(data)} 条历史问答...")
    for i, qa in enumerate(data):
        text = f"问题: {qa['question']}\n回答: {qa['answer']}\n类别: {qa.get('category','咨询')}"
        meta = {"title": qa["question"][:100], "question": qa["question"],
                "answer": qa["answer"], "category": qa.get("category", "咨询"),
                "department": qa.get("department", ""),
                "tags": ",".join(qa.get("tags", [])), "type": "qa_pair"}
        kb.add(HISTORY_KB, text, meta, f"seed_{i}")
    print(f"  完成! 历史KB: {kb.count(HISTORY_KB)}条")

def import_materials():
    d = Path(__file__).parent / "materials"
    if not d.exists(): return print(f"  {d} 不存在")
    files = sorted(d.glob("*.txt"))
    print(f"  导入 {len(files)} 份材料文档...")
    idx = 0
    for fp in files:
        content = fp.read_text(encoding="utf-8")
        sections = [s.strip() for s in content.split("\n\n") if len(s.strip()) > 30]
        for sec in sections:
            fl = sec.split("\n")[0].lstrip("# ").strip()
            stitle = fl if len(fl) > 5 else fp.stem
            meta = {"title": f"{fp.stem} - {stitle[:50]}", "source": fp.name,
                    "type": "document", "category": "制度文件", "tags": fp.stem}
            kb.add(MATERIAL_KB, sec, meta, f"seed_mat_{idx}")
            idx += 1
    print(f"  完成! 材料KB: {kb.count(MATERIAL_KB)}条")

if __name__ == "__main__":
    print("=" * 50)
    print("  种子数据导入")
    print("=" * 50)
    import_history()
    import_materials()
    print(f"\n总计: 历史{kb.count(HISTORY_KB)}条, 材料{kb.count(MATERIAL_KB)}条")
    print("导入完成!")
