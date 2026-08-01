"""
ChromaDB 双知识库测试脚本
测试 KBManager 的所有功能
"""
import time
from kb_service import kb, HISTORY_KB, MATERIAL_KB, TOP_K


def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)
    
def test_count():
    """测试统计文档数量"""
    print_section("测试统计文档数量")
    
    history_count = kb.count(HISTORY_KB)
    material_count = kb.count(MATERIAL_KB)
    
    print(f"  历史知识库文档数: {history_count}")
    print(f"  材料知识库文档数: {material_count}")
    print(f"  总文档数: {history_count + material_count}")

def test_search():
    history_results = kb.search(HISTORY_KB, "食堂", top_k=2)
    print(f"  总文档数: {history_results}")
test_search()