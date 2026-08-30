# 文档知识库 RAG 设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: 语义记忆 spec(RAG ①)、MVP spec

## 1. 背景

语义记忆(①)完成了对话记忆的向量检索。本篇做 RAG 完整工程形态:**私有文档知识库**——用户把 Markdown 放 `docs_kb/`,agent 通过 `search_docs` 工具语义检索并引用回答。核心学习点:**chunking**。

## 2. 目标

- `python -m agent_radar.kb` 入库(切块 + embedding + SQLite)
- `search_docs(query, n=3)` 工具:语义检索 top-k 文档块
- 专家 / 系统提示提示可用知识库

## 3. 方案(标题切块 + 全量重建 + 复用 embedder)

- 切块:Markdown 标题(`##` 级及以上)为界;单节 >500 字按段落累积再切;小节顺序合并;**不重叠**
- 入库:**清空 `kb_chunks` 全量重建**(文档变重跑)
- 检索:复用 `cosine_similarity` + `ZhipuEmbeddingClient`,**无新依赖**

## 4. 组件

### 4.1 `store/kb.py`
- `kb_chunks` 表(id / doc / content / embedding)——`db.init_db` 建表
- `chunk_markdown(text, max_chars=500) -> list[str]`
- `ingest_kb(conn, docs_dir, embedder) -> int`:扫 `*.md`,切块、embed、清空重建,返回块数;embedder None 或目录不存在 → 返回 0
- `search_kb(conn, query_embedding, n=3) -> list[{doc, content, score}]`

### 4.2 `tools/kb.py`
- `SEARCH_SPEC`:`search_docs(query 必填, n=3)`
- `make_tool(conn, embedder=None)`:embed(query)→ `search_kb` → JSON;embedder None → 提示字符串;embed 失败 → 错误字符串(**不崩**);空结果 → 提示先入库

### 4.3 `agent_radar/kb.py`(入口)
- `main()`:load config → conn → embedder → `ingest_kb(conn, "docs_kb", embedder)` → 打印块数;`docs_kb/` 不存在 → SystemExit 提示创建

### 4.4 `cli.py`
- `build_registry` 注册 `search_docs`(传 conn + embedder)

### 4.5 提示词
- `SYSTEM_PROMPT`(loop.py)与专家 `_COMMON`(experts.py)各加一句:涉及私有文档 / 资料的问题可用 `search_docs` 检索知识库

## 5. 数据流

```
docs_kb/*.md → python -m agent_radar.kb(切块+embed 入库)
→ 用户提问 → 专家调 search_docs → 余弦 top-k 块 → 引用文档回答
```

## 6. 约束

- 无新依赖;复用 embedding / cosine 基础设施
- 全量重建;检索降级返回字符串不崩
- `docs_kb/` 不存在 → ingest 返回 0 / kb 命令提示
- `.gitignore` 不忽略 `docs_kb/`(用户自行决定是否提交文档)

## 7. 测试(全 mock)

- `chunk_markdown`:大节分开、小节合并、超长节按段拆、空文本
- `ingest_kb`:tmp 目录 + 假 embedder 入库计数、重跑清旧、无目录 / 无 embedder 返回 0
- `search_kb`:top-k 顺序与字段
- db:`init_db` 建 `kb_chunks` 表
- tools:检索路径、embedder None、embed 失败、空结果提示
- kb main:无 docs_kb → SystemExit
- cli:`build_registry` 含 `search_docs`;提示词含 `search_docs` 引用

## 8. 范围(本次)

- ✅ 文档 KB MVP(Markdown、标题切块、全量重建)
- ❌ 增量入库、重叠窗口、PDF/Word 格式、rerank、混合检索
