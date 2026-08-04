# Phase 3b:手动简报 + 邮件推送 设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: MVP / Phase 2 / Phase 3a specs

## 1. 背景

Phase 3b 给 AgentRadar 加「简报」能力:一条命令生成综合周报(趋势 + 就业 + 行业)并通过邮件发出。**手动触发**(无调度),定时交给系统任务计划程序 / cron。

## 2. 目标

`python -m agent_radar.brief` → 对趋势 / 就业 / 行业各调维度专家生成一段 → 拼综合简报 → SMTP 发邮件。无 SMTP 配置则只打印到终端。

## 3. 方案(复用专家 + 标准库 SMTP)

- 复用 `EXPERT_PROMPTS` + `AgentLoop` + `ResilientClient` + `registry`(与对话同一套)
- 邮件用标准库 `smtplib`(**无新依赖**)
- 手动触发;无调度、无常驻进程

## 4. 组件

### 4.1 `agent_radar/brief.py`
- `REPORT_DIMS = [("trend","技术趋势"),("jobs","就业行情"),("industry","行业动态")]`
- `generate_brief(client, registry, max_iterations=8) -> str`:对每个 dim 构造 `AgentLoop(EXPERT_PROMPTS[dim])` 跑一个简报问题,拼接成 `# AgentRadar 周报` + 三段
- `main()`:load config → build client/registry → `generate_brief` → 若配齐 SMTP 则 `send_email`,否则 `print`

### 4.2 `agent_radar/notify.py`
- `send_email(subject, body, config) -> bool`:`smtplib`(SSL/TLS)登录 + `sendmail`;异常捕获返回 `False`(不让邮件错误崩掉 brief)

### 4.3 `config.py`
新增可选字段:`smtp_host: str | None`、`smtp_port: int = 0`、`smtp_user: str | None`、`smtp_pass: str | None`、`email_to: str | None`

### 4.4 `.env.example`
`SMTP_*` 示例(QQ / 163)

## 5. 数据流

```
python -m agent_radar.brief
  → generate_brief(趋势段 + 就业段 + 行业段)
  → [有 SMTP 配置] send_email → 收件箱
  → [无 SMTP 配置] print 到终端
```

## 6. 约束

- `smtplib` 标准库,**无新依赖**
- 简报复用现有专家(`ResilientClient` GLM→DeepSeek 兜底自动适用)
- 简报**不含 learning 段**(个性化对话场景,不适合通用推送)
- 无 SMTP 配置 → **只打印不发**
- `send_email` 异常捕获,返回 `False`(邮件失败不崩 brief)

## 7. 测试(全 mock,不联网)

- `generate_brief`:mock client(每专家返回一段),验证 3 段 + 标题 + 各 dim prompt 被用
- `send_email`:mock `smtplib.SMTP_SSL`,验证 `login` + `sendmail` 调用;模拟异常 → 返回 `False`
- 无 SMTP 配置:`main` 只打印、不调 `send_email`

## 8. 范围(本次)

- ✅ 综合简报 + SMTP(手动触发)
- ❌ 定时调度(交给系统任务计划)
- ❌ Web UI(3c)、其他渠道(微信 / 飞书)
- ❌ learning 段
