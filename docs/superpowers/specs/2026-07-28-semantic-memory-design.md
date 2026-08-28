# RAG 语义记忆设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: MVP spec(memory 部分)

## 1. 背景

现有对话记忆是「最近 N 条」时间序,agent 想不起早期相关对话。升级为**语义记忆(RAG)**:embedding + 余弦检索 top-k 相关记忆。补齐知识图谱的 RAG 环。

## 2. 目标

- `write_memory` 自动 embedding 存储
- `read_memory(query, n=5)` 语义检索(余弦 top-k)
- 全链路降级(embedder 缺 / 失败 → 时间序,不崩)

## 3. 方案(智谱 embedding + SQLite 向量列 + 纯 Python 余弦)

- `ZhipuEmbeddingClient`(zhipuai SDK,复用现有 `ZHIPU_API_KEY`)
- memory 表加 `embedding` 列(JSON 文本,可空;`ALTER TABLE` 自动迁移旧库)
- `search_memory`:读全部向量,纯 Python 余弦相似,top-k
- **无新依赖**(不用 numpy / faiss / 向量库;记忆条数小,纯 Python 够)

## 4. 组件

### 4.1 `llm/client.py`
- `ZhipuEmbeddingClient(api_key, model="embedding-2")`,`.embed(text) -> list[float]`
- 模块级 `cosine_similarity(a, b) -> float`(纯 Python 点积 / 模长)

### 4.2 `store/db.py`(迁移)
- `_SCHEMA` 的 memory 表加 `embedding TEXT`(新库直接含)
- `init_db` 后 `try: ALTER TABLE memory ADD COLUMN embedding TEXT / except OperationalError: pass`(旧库迁移,列已存在则忽略)

### 4.3 `store/memory.py`
- `append_memory(conn, role, content, embedding=None)`(embedding 为 `list[float]`,存 JSON 文本)
- `search_memory(conn, query_embedding, n=5) -> list[dict]`:读全部(带向量)条目,余弦排序,top-k(跳过无向量)
- `list_recent(conn, n)` 保留(降级路径)

### 4.4 `tools/memory.py`
- `READ_SPEC`:`read_memory(query: str 必填, n: int = 5)`
- `make_read_tool(conn, embedder)`:embed(query)→ search;**embedder 为 None 或 embed 抛错 → `list_recent` 降级**
- `make_write_tool(conn, embedder)`:embed 成功 → 存向量;失败 → 存文本不带向量
- 工厂签名:`make_*_tool(conn, embedder=None)`

### 4.5 `cli.py`
- `build_registry(conn, github, embedder=None)`(新参数,默认 None 保持兼容)
- `main` 构造 `ZhipuEmbeddingClient(config.zhipu_api_key)` 注入

## 5. 降级矩阵

| 情况 | 行为 |
|---|---|
| embedder 未配置(key 缺 / None) | read / write 全走旧时间序逻辑 |
| embedding 调用失败 | write 不带向量 / read 降级时间序,**不崩** |
| 旧数据(无向量) | search 时跳过 |

## 6. 测试(全 mock,不联网)

- `ZhipuEmbeddingClient.embed`(mock zhipuai SDK)
- `cosine_similarity` 数学断言(同向 = 1、正交 = 0)
- `search_memory`:已知向量 top-k 顺序正确、跳过空向量、不足 n 返回全部
- tools:read 语义路径(mock embedder)/ 降级路径(mock 抛错 → 时间序);write 存向量 / 失败降级
- db 迁移:旧库(无列)init 后可写读向量
- 受签名影响的旧测试更新(read_memory spec、make_*_tool 调用)

## 7. 范围(本次)

- ✅ 语义记忆 MVP(embedding + 余弦 + 降级)
- ❌ 文档知识库 RAG(方案②,后续)
- ❌ numpy / faiss / 向量数据库
