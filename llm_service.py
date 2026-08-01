"""
LLM 调用服务: 意图识别 + 回答生成 + 纪要生成
支持 OpenAI 原生客户端和 liteLLM 两种模式
"""
import json
import os
from openai import OpenAI
from litellm import completion as litellm_completion
from config import LLM_KEY, LLM_URL, LLM_MODEL, MAX_FOLLOWUP

# ==================== 全局配置 ====================

# 控制使用哪种 LLM 调用方式: "openai" 或 "litellm"
LLM_MODE = "litellm"  # 改为 "openai" 使用原生 OpenAI 客户端

_client = None
_demo = not LLM_KEY


def get_llm_mode():
    """获取当前 LLM 模式"""
    return LLM_MODE


def set_llm_mode(mode):
    """动态切换 LLM 模式"""
    global LLM_MODE
    if mode not in ["openai", "litellm"]:
        raise ValueError(f"不支持的 LLM 模式: {mode}，请使用 'openai' 或 'litellm'")
    LLM_MODE = mode
    print(f"[LLM] 模式已切换为: {mode}")


def client():
    """获取 OpenAI 客户端（仅在 openai 模式下使用）"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=LLM_KEY, base_url=LLM_URL)
    return _client


def is_demo():
    """是否为演示模式"""
    return _demo


# ==================== 通用 LLM 调用封装 ====================

def _call_llm(messages, temperature=0.3, max_tokens=2000, response_format=None):
    """
    统一的 LLM 调用接口
    根据 LLM_MODE 自动选择调用方式
    """
    if LLM_MODE == "openai":
        return _call_openai(messages, temperature, max_tokens, response_format)
    elif LLM_MODE == "litellm":
        return _call_litellm(messages, temperature, max_tokens, response_format)
    else:
        raise ValueError(f"未知的 LLM 模式: {LLM_MODE}")


def _call_openai(messages, temperature, max_tokens, response_format):
    """使用 OpenAI 原生客户端调用"""
    kwargs = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    if response_format:
        kwargs["response_format"] = response_format
    
    response = client().chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _call_litellm(messages, temperature, max_tokens, response_format):
    """使用 liteLLM 调用"""
    # liteLLM 需要设置环境变量
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = LLM_KEY
    
    kwargs = {
        "model": f"openai/{LLM_MODEL}",  # liteLLM 格式: provider/model
        "messages": messages,
        "api_base": LLM_URL,
        "api_key": LLM_KEY,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    # liteLLM 的 response_format 处理
    if response_format and response_format.get("type") == "json_object":
        kwargs["response_format"] = {"type": "json_object"}
    
    response = litellm_completion(**kwargs)
    return response.choices[0].message.content


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
        content = _call_llm(
            messages=[
                {"role": "system", "content": INTENT_P},
                {"role": "user", "content": msg}
            ],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        print(f"### LLM raw ({LLM_MODE}): {content}")
        d = json.loads(content)
        print(f"### LLM Res: {d}")
        
        clear = d.get("is_clear", True) or round_num >= MAX_FOLLOWUP
        fu = d.get("follow_up") if not clear else None
        return clear, fu, d.get("data") if clear else None
        
    except Exception as e:
        print(f"[analyze] LLM异常 ({LLM_MODE}), 降级处理: {e}")
        # 降级: 如果问题太短, 追问一下
        if len(question) < 8:
            return False, "请详细描述你的问题, 例如涉及什么业务、遇到什么困难?", None
        return True, None, {
            "category": "其他", 
            "intent": "未识别",
            "urgency": "普通", 
            "department": None,
            "keywords": [], 
            "refined": question, 
            "context": None
        }


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
    return True, None, {
        "category": cat, 
        "intent": intent,
        "urgency": "普通", 
        "department": None,
        "keywords": kws, 
        "refined": question, 
        "context": None
    }


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
            return f"[演示模式] 根据材料库匹配:\n\n{refs_text[:1000]}\n\n---\n请配置 LLM_KEY 启用完整AI能力。"
        return "[演示模式] 未找到匹配,请配置 API Key。"

    prompt = GEN_P.format(
        refs=refs_text or "无可参考资料",
        category=structured.get("category", ""),
        intent=structured.get("intent", ""),
        question=structured.get("refined", "")
    )
    
    try:
        content = _call_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        return content
    except Exception as e:
        print(f"[generate_answer] 生成失败 ({LLM_MODE}): {e}")
        return f"生成失败: {e}"


# ==================== 纪要生成 ====================

SUM_P = """基于以下信息生成解决纪要。输出JSON:

问题: {q}
类别: {cat} | 意图: {intent}
回答: {a}
来源: {src}

JSON: {{"summary":"纪要全文","kb_q":"知识库问题摘要","kb_a":"知识库答案(200字)","score":0.85}}"""


def generate_summary(question, category, intent, answer, source):
    """生成解决纪要"""
    if is_demo():
        return {
            "summary": f"[演示] {question[:100]}\n{answer[:200]}",
            "kb_q": question[:100], 
            "kb_a": answer[:200], 
            "score": 0.7
        }

    try:
        content = _call_llm(
            messages=[{
                "role": "user", 
                "content": SUM_P.format(
                    q=question[:500], 
                    cat=category, 
                    intent=intent,
                    a=answer[:2000], 
                    src=source
                )
            }],
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        return json.loads(content)
        
    except Exception as e:
        print(f"[generate_summary] 生成失败 ({LLM_MODE}): {e}")
        return {
            "summary": f"{question[:100]}\n{answer[:200]}",
            "kb_q": question[:100], 
            "kb_a": answer[:200], 
            "score": 0.5
        }


# ==================== 模式切换与测试 ====================

def test_llm_modes():
    """测试两种 LLM 模式"""
    test_question = "我的工资怎么还没发？"
    
    print("=" * 60)
    print("测试 OpenAI 模式")
    print("=" * 60)
    set_llm_mode("openai")
    clear, follow_up, data = analyze(test_question)
    print(f"清晰: {clear}, 追问: {follow_up}, 数据: {data}")
    
    print("\n" + "=" * 60)
    print("测试 liteLLM 模式")
    print("=" * 60)
    set_llm_mode("litellm")
    clear, follow_up, data = analyze(test_question)
    print(f"清晰: {clear}, 追问: {follow_up}, 数据: {data}")


def get_mode_info():
    """获取当前模式信息"""
    return {
        "mode": LLM_MODE,
        "demo": is_demo(),
        "model": LLM_MODEL,
        "url": LLM_URL,
        "has_key": bool(LLM_KEY)
    }


if __name__ == "__main__":
    # 查看当前配置
    print("当前 LLM 配置:")
    print(json.dumps(get_mode_info(), indent=2, ensure_ascii=False))
    
    # 测试
    if not is_demo():
        test_llm_modes()