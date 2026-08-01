# 基层问题解决中心

基于 AI 的基层问题解决中心 —— 双路 RAG 检索 + 自进化知识库。

## 核心思路

```
用户输入问题
    │
    ▼
意图识别 + 结构化（多轮追问补全）
    │
    ▼
┌─ 历史问题知识库 ─┐
│  ChromaDB 检索     │
│  相似度 ≥ 0.70?   │── 是 ──→ 直接返回历史回答
│  相似度 ≥ 0.45?   │── 是 ──→ 展示参考给用户
└──────────────────┘
    │ 否
    ▼
┌─ 材料知识库 ─────┐
│  ChromaDB 检索     │
│  + LLM 生成回答    │
└──────────────────┘
    │
    ▼
用户反馈 ──→ 已解决 ──→ AI生成纪要 ──→ 管理员审核 ──→ 入库历史KB
         ──→ 未解决 ──→ 管理员端可见，人工跟进
```

- **历史问题知识库**：基于历史问答记录，用于相似问题快速答复
- **材料知识库**：基于规章制度、业务指导书，用于补充生成回答
- **自进化**：用户确认解决 → AI 自动总结 → 管理员审核 → 入库，知识库持续增长

## 环境要求

- Python 3.10（conda `ltz` 环境）
- ChromaDB 1.5+
- Flask 3.1+
- SQLAlchemy 2.0+
- OpenAI SDK（调用 DeepSeek API，可选）

## 快速开始

### 1. 激活环境

```powershell
# 使用已有的 conda ltz 环境
conda activate ltz
```

### 2. 安装依赖

```powershell
pip install flask openai sqlalchemy chromadb
```

### 3. 导入种子数据

```powershell
python seed_data/import_seed.py
```

成功输出：
```
==================================================
  种子数据导入
==================================================
  导入 10 条历史问答...
  完成! 历史KB: 10条
  导入 5 份材料文档...
  完成! 材料KB: 18条

总计: 历史10条, 材料18条
导入完成!
```

### 4. 启动服务

```powershell
python app.py
```

```
==================================================
  基层问题解决中心 v2.0
  演示模式: 否 (LLM已连接)
  历史KB: 10条 | 材料KB: 18条
  地址: http://localhost:8100
==================================================
```

### 5. 打开浏览器

```
http://localhost:8100
```

## API Key 配置（可选）

不配置 API Key 时自动进入**演示模式**（关键词匹配 + 模板回答）。

```powershell
$env:DEEPSEEK_API_KEY="sk-xxxxxxxx"
```

| 功能 | 演示模式 | 完整模式 |
|------|---------|---------|
| 意图识别 | 关键词规则匹配 | DeepSeek LLM |
| 向量 Embedding | all-MiniLM-L6-v2 | 同左 |
| 回答生成 | 模板拼接检索结果 | DeepSeek LLM + RAG |
| 纪要生成 | 简单模板 | DeepSeek LLM |

## API 接口

### 用户端

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ask` | 提交问题/追问回复 |
| POST | `/api/feedback` | 用户反馈（已解决/未解决） |

**提交问题：**
```json
POST /api/ask
{
    "question": "6月绩效少了500元怎么办?",
    "session_id": null
}

// 响应
{
    "question_id": "xxx",
    "status": "已回答",
    "structured": {
        "category": "投诉",
        "intent": "薪资核查",
        "keywords": ["绩效", "工资"]
    },
    "message": "根据历史记录...",
    "source": "history_kb"
}
```

**用户反馈：**
```json
POST /api/feedback
{
    "question_id": "xxx",
    "resolved": true,
    "satisfaction": 5
}
```

### 管理员端

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/dashboard` | 仪表盘统计 |
| GET | `/api/admin/reviews?status=pending` | 待审核列表 |
| POST | `/api/admin/reviews/:id/approve` | 审核通过（自动入库） |
| POST | `/api/admin/reviews/:id/reject` | 审核驳回 |
| GET | `/api/admin/unresolved` | 未解决问题列表 |
| GET | `/api/admin/kb/:kb_name` | 知识库条目列表 |
| POST | `/api/admin/kb/:kb_name/add` | 手动添加条目 |
| PUT | `/api/admin/kb/:kb_name/:id` | 编辑知识库条目 |
| DELETE | `/api/admin/kb/:kb_name/:id` | 删除条目 |

## 项目结构

```
center-new/
├── app.py                # Flask 主应用（所有路由）
├── config.py             # 全局配置
├── kb_service.py         # ChromaDB 双知识库管理
├── llm_service.py        # LLM 调用（意图/回答/纪要）
├── models.py             # SQLite 数据库模型
├── static/
│   └── index.html        # Vue.js 单页前端
├── seed_data/
│   ├── history_qa.json   # 10 条种子历史问答
│   ├── materials/        # 5 份制度文档
│   │   ├── 考勤与休假管理制度.txt
│   │   ├── 差旅费管理办法.txt
│   │   ├── 员工医疗与福利政策.txt
│   │   ├── IT设备管理与报修规范.txt
│   │   └── 内部岗位调动管理办法.txt
│   └── import_seed.py    # 种子数据导入脚本
├── data/
│   ├── chromadb/         # ChromaDB 持久化目录
│   └── center.db         # SQLite 业务数据库
└── test_e2e.py           # 端到端测试
```

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Flask 3.1 | 轻量级 Web 框架 |
| 前端 | Vue.js 3 (CDN) | 单页应用，员工端+管理员端 |
| 向量数据库 | ChromaDB 1.5 | 持久化语义检索 |
| Embedding | all-MiniLM-L6-v2 | 384维，ChromaDB 内置 |
| LLM | DeepSeek API | 意图识别/回答生成/纪要 |
| 业务数据库 | SQLite | 问题记录、审核记录 |
| 文档解析 | 纯文本分段 | 按空行分段导入材料KB |

## 检索策略说明

| 相似度区间 | 处理方式 |
|-----------|---------|
| ≥ 0.70 | **高分**：直接返回历史回答，用户只需确认 |
| 0.45 ~ 0.70 | **中分**：展示历史参考，用户自判是否解决 |
| < 0.45 | **无匹配**：走材料库 + LLM 生成新回答 |

阈值可在 `config.py` 中调整：
```python
HIGH_SIM = 0.70      # 直接采纳阈值
MEDIUM_SIM = 0.45    # 展示参考阈值
```

## 端到端测试

```powershell
python test_e2e.py
```
