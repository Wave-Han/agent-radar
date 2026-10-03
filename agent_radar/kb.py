"""Knowledge-base ingestion entrypoint: chunk + embed docs_kb/*.md into SQLite."""
import os

from agent_radar.config import ensure_utf8_stdout, load_config
from agent_radar.store.db import get_connection, init_db


def main() -> None:
    ensure_utf8_stdout()
    from agent_radar.llm.client import ZhipuEmbeddingClient
    from agent_radar.store.kb import ingest_kb

    config = load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")
    if not os.path.isdir("docs_kb"):
        raise SystemExit("未找到 docs_kb/ 目录——请创建它并放入 Markdown 文档后重试。")

    conn = get_connection(config.db_path)
    init_db(conn)
    embedder = ZhipuEmbeddingClient(config.zhipu_api_key)
    n = ingest_kb(conn, "docs_kb", embedder)
    print(f"知识库入库完成:共 {n} 个块(来源 docs_kb/*.md)。")


if __name__ == "__main__":
    main()
