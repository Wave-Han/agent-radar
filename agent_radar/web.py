"""Web UI: FastAPI app + single-page HTML (chat + weekly brief)."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent_radar.agent.loop import Answer
from agent_radar.config import load_config


class ChatIn(BaseModel):
    message: str = ""


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>AgentRadar</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; }
h1 { font-size: 1.4rem; }
#log { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; height: 360px; overflow-y: auto; margin: 1rem 0; background: #fafafa; }
.msg { margin: 0.5rem 0; white-space: pre-wrap; }
.you { color: #555; }
.bot { color: #111; font-weight: 500; }
.tools { color: #888; font-size: 0.85rem; }
.row { display: flex; gap: 0.5rem; }
input { flex: 1; padding: 0.5rem; font-size: 1rem; }
button { padding: 0.5rem 1rem; font-size: 1rem; cursor: pointer; }
#brief { white-space: pre-wrap; border-top: 1px solid #ddd; margin-top: 1rem; padding-top: 1rem; }
</style>
</head>
<body>
<h1>AgentRadar <small>(多 agent · 四维度)</small></h1>
<div id="log"></div>
<div class="row">
  <input id="msg" placeholder="提问,如:现在做 AI agent 该重点学什么?" autofocus>
  <button id="send">发送</button>
  <button id="brief-btn">生成周报</button>
</div>
<pre id="brief"></pre>
<script>
const log = document.getElementById("log");
const msg = document.getElementById("msg");
function add(cls, text) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
async function send() {
  const text = msg.value.trim();
  if (!text) return;
  add("you", "你: " + text);
  msg.value = "";
  const r = await fetch("/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: text})});
  const data = await r.json();
  add("bot", "AgentRadar: " + data.content);
  if (data.tools_used && data.tools_used.length) {
    const t = document.createElement("div");
    t.className = "tools";
    t.textContent = "(使用工具: " + data.tools_used.join(", ") + ")";
    log.appendChild(t);
    log.scrollTop = log.scrollHeight;
  }
}
document.getElementById("send").addEventListener("click", send);
msg.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
document.getElementById("brief-btn").addEventListener("click", async () => {
  document.getElementById("brief").textContent = "生成中(可能几十秒)...";
  const r = await fetch("/brief", {method: "POST"});
  const data = await r.json();
  document.getElementById("brief").textContent = data.brief;
});
</script>
</body>
</html>
"""


def build_app(orchestrator, brief_fn):
    """Build the FastAPI app with injected orchestrator + brief function."""
    app = FastAPI(title="AgentRadar")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return INDEX_HTML

    @app.post("/chat")
    def chat(chat_in: ChatIn):
        ans: Answer = orchestrator.run(chat_in.message)
        return {"content": ans.content, "tools_used": ans.tools_used}

    @app.post("/brief")
    def brief():
        return {"brief": brief_fn()}

    return app


def main():
    import uvicorn
    from agent_radar.agent.orchestrator import Orchestrator
    from agent_radar.brief import generate_brief
    from agent_radar.cli import build_client, build_registry
    from agent_radar.data.github_client import GitHubClient
    from agent_radar.store.db import get_connection, init_db

    config = load_config()
    if not config.zhipu_api_key:
        raise SystemExit("缺少 ZHIPU_API_KEY,请在 .env 中配置(参考 .env.example)。")

    conn = get_connection(config.db_path)
    init_db(conn)
    client = build_client(config)
    registry = build_registry(conn, GitHubClient(token=config.github_token))
    orchestrator = Orchestrator(client, registry, max_iterations=config.max_iterations)
    brief_fn = lambda: generate_brief(client, registry, max_iterations=config.max_iterations)
    app = build_app(orchestrator, brief_fn)
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
