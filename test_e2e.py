"""端到端测试 — ChromaDB 版本"""
import sys
sys.path.insert(0, ".")
from kb_service import kb
from llm_service import analyze, generate_answer, generate_summary, is_demo
from config import HISTORY_KB, MATERIAL_KB

print("=" * 50)
print(f"  模式: {'演示' if is_demo() else '完整 (LLM已连接)'}")
print(f"  历史KB: {kb.count(HISTORY_KB)}条 | 材料KB: {kb.count(MATERIAL_KB)}条")
print("=" * 50)

# 1. 意图识别
print("\n>>> 1. 意图识别")
q = "我6月的绩效工资少了500元,不知道找谁处理"
clear, fu, data = analyze(q)
print(f"  输入: {q}")
print(f"  清晰: {clear}, 追问: {fu}")
print(f"  类别: {data['category']} | 意图: {data['intent']}")
print(f"  关键词: {data.get('keywords',[])}")

# 2. 历史KB检索
print("\n>>> 2. 历史KB检索 (ChromaDB embedding)")
query = data.get("refined", q)
hist = kb.search(HISTORY_KB, query, 3)
for i, r in enumerate(hist):
    m = r["metadata"]
    print(f"  [{i+1}] sim={r['similarity']:.4f} | {m.get('title','')[:60]}")

if hist and hist[0]["similarity"] >= 0.70:
    print("  → 高分匹配! 可直接返回历史回答")
elif hist and hist[0]["similarity"] >= 0.45:
    print("  → 中分匹配, 展示参考")

# 3. 材料KB检索
print("\n>>> 3. 材料KB检索")
mat = kb.search(MATERIAL_KB, query, 3)
for i, r in enumerate(mat):
    print(f"  [{i+1}] sim={r['similarity']:.4f} | {r['metadata'].get('title','')[:60]}")

# 4. 回答生成
print("\n>>> 4. 回答生成")
refs = ""
if mat:
    refs = "\n\n".join([f"### {r['metadata'].get('title','')}\n{r['document'][:300]}" for r in mat[:2]])
answer = generate_answer(data, refs)
print(f"  {answer[:200]}...")

# 5. 纪要生成
print("\n>>> 5. 纪要生成")
s = generate_summary(q, data["category"], data["intent"], answer, "material_kb")
print(f"  纪要: {s.get('summary','')[:150]}")
print(f"  KB问答: Q={s.get('kb_q','')[:60]}")

print("\n" + "=" * 50)
print("  全部测试通过! (ChromaDB)")
print("=" * 50)
