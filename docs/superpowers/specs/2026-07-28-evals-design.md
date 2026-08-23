# 路由评估 Evals MVP 设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: Phase 3a 多 agent spec

## 1. 背景

AgentRadar 已多 agent 化(Orchestrator 路由 + 5 维度专家),但无法量化路由质量。Evals MVP 先做**路由评估**:固定问题集 → `route` → 对比期望维度 → 准确率。

## 2. 目标

`python -m agent_radar.evals` 跑内置评估集,输出路由准确率报告。

## 3. 方案(纯逻辑可测 + 注入 route_fn)

`evals.py` 一个文件:`EVAL_CASES`(内置问题集)+ `run_evals(route_fn, cases)`(纯逻辑)+ `print_report(summary)` + `main()`(构造 Orchestrator 只用其 `route`)。

## 4. 组件(`agent_radar/evals.py`)

- **`EVAL_CASES: list[tuple[str, str]]`** — 约 16 题,每维度 3~4 题,题面刻意避免模糊
- **`run_evals(route_fn, cases=EVAL_CASES) -> dict`** — 返回:
  `{total, passed, accuracy(0~1 float), results: [{question, expected, actual, passed}], by_dim: {dim: {passed, total}}}`
- **`print_report(summary) -> None`** — 终端打印:每题 `[PASS/FAIL]` + 期望→实际、总结准确率、分维度统计
- **`main()`** — `load_config` → `build_client` → `Orchestrator(client, ToolRegistry())`(route 不用 registry)→ `run_evals(orch.route)` → `print_report`

## 5. 约束

- `run_evals` / `print_report` 纯逻辑(注入 `route_fn`),单元测试**全 mock 不联网**
- `EVAL_CASES` 校验:每题 expected ∈ `DIMENSIONS`;题面唯一;总数 ≥ 12;覆盖全部 5 个维度
- 真实跑需 `ZHIPU_API_KEY`,约 17 次轻量 route 调用(成本很低)
- 英文标识符 / 注释;报告文案中文

## 6. 测试(全 mock)

- `run_evals`:fake `route_fn`(全对 → accuracy 1.0;部分错 → 明细与 by_dim 正确)
- `EVAL_CASES` 格式:expected 合法、题目唯一、≥12 题、覆盖 5 维度
- `print_report`:输出含准确率与 FAIL 标记(capsys)

## 7. 范围(本次)

- ✅ 路由评估 MVP(评估集 + 评估器 + 报告 + 命令)
- ❌ 回答质量 LLM-as-judge(后续)
- ❌ CI / 定时自动跑
