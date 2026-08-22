"""Web UI: FastAPI app + single-page HTML (chat + weekly brief)."""
import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

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
button:disabled { cursor: default; opacity: 0.5; }
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
const DIM_NAMES = {trend: "技术趋势", jobs: "就业行情", industry: "行业动态", learning: "学习方向", general: "通用"};
function add(cls, text) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}
async function send() {
  const text = msg.value.trim();
  if (!text) return;
  add("you", "你: " + text);
  msg.value = "";
  const sendBtn = document.getElementById("send");
  sendBtn.disabled = true;
  const thinking = add("bot", "AgentRadar: 思考中...");
  try {
    const r = await fetch("/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: text})});
    if (!r.body || !r.body.getReader) {
      const data = await r.json();
      thinking.textContent = "AgentRadar: " + data.content;
      return;
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    thinking.textContent = "AgentRadar: ";
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});
      let sep;
      while ((sep = buf.indexOf("\\n\\n")) >= 0) {
        const block = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        for (const line of block.split("\\n")) {
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") continue;
          let ev;
          try { ev = JSON.parse(payload); } catch { continue; }
          if (ev.type === "route") {
            thinking.textContent += "\\n[已路由:" + (DIM_NAMES[ev.dim] || ev.dim) + "]\\n";
          } else if (ev.type === "delta") {
            thinking.textContent += ev.content;
          } else if (ev.type === "tool") {
            thinking.textContent += "\\n[调用工具:" + ev.name + "]";
          } else if (ev.type === "error") {
            thinking.textContent += "\\n⚠️ " + ev.message;
          }
          log.scrollTop = log.scrollHeight;
        }
      }
    }
  } catch (e) {
    thinking.textContent += "\\n请求失败,请重试。(" + e + ")";
  } finally {
    sendBtn.disabled = false;
  }
}
document.getElementById("send").addEventListener("click", send);
msg.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
document.getElementById("brief-btn").addEventListener("click", async () => {
  const btn = document.getElementById("brief-btn");
  btn.disabled = true;
  document.getElementById("brief").textContent = "生成中(可能几十秒)...";
  try {
    const r = await fetch("/brief", {method: "POST"});
    const data = await r.json();
    document.getElementById("brief").textContent = data.brief;
  } catch (e) {
    document.getElementById("brief").textContent = "周报生成失败,请重试。(" + e + ")";
  } finally {
    btn.disabled = false;
  }
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
        def gen():
            try:
                for ev in orchestrator.run_stream(chat_in.message):
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            except Exception as e:  # noqa: BLE001 - surface as an SSE error event
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

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
