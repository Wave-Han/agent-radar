# 回答质量 Evals(LLM-as-Judge)设计文档

- 日期: 2026-10-04
- 状态: Approved
- 关联: 路由 Evals spec、learning-map 中期路线

## 1. 背景

路由 Evals(18/18 = 100%)验证了"分对了没"。质量 Evals 验证"答好了没":agent 跑完整流程后,用一次 LLM 调用当评审员,对照预设标准逐条 PASS/FAIL。

## 2. 目标

`python -m agent_radar.eval_quality` → 每题跑完整 agent → LLM judge 打分 → 终端报告。

## 3. 方案(LLM-as-Judge + 严格提示防偏)

- **5 题评估集**:每维度一题,每题 2-4 条标准(格式合规 / 内容覆盖 / 个性化)
- **Judge prompt**:严格措辞("不满足即 FAIL"),固定输出格式(标准N: PASS/FAIL + 总分 X/Y)
- **解析**:逐条匹配"标准N"+ PASS/FAIL,未匹配到为 None(不计入 passed)
- **入口**:`python -m agent_radar.eval_quality [limit]`(limit 可限制题数做 smoke)

## 4. 组件(`agent_radar/eval_quality.py`)

- `QUALITY_CASES: list[dict]`(question + criteria)
- `JUDGE_PROMPT`(严格 + 固定格式)
- `judge_answer(client, question, criteria, answer) -> dict`(results/passed/total)
- `_parse_judge_response(text, n_criteria) -> dict`
- `run_quality_evals(orchestrator, client, cases) -> dict`(总标准通过率)
- `print_quality_report(summary)` + `main(limit=None)`

## 5. 约束

- judge 用同一个 client(继承 fallback)
- 每题 = 完整 agent 跑(多轮)+ 1 次 judge ≈ 成本高,支持 limit
- judge 解析失败的标准标 None(不猜)
- 测试全 mock 不联网

## 6. 测试

- case 格式(≥5 题、每题 ≥2 标准)
- parse(完整 / 缺行 / 全 FAIL)
- judge_answer(mock client)
- run_quality_evals(mock orch + client)

## 7. 范围

- ✅ CLI 版、5 题、逐条 PASS/FAIL
- ❌ Web 集成、judge 打 1-5 分制、自动重试 judge
