# Phase 2:就业行情 + 行业动态 设计文档

- 日期: 2026-07-28
- 状态: Approved
- 关联: AgentRadar MVP spec、DeepSeek fallback spec

## 1. 背景

MVP 覆盖「技术生态趋势 + 学习路径」。Phase 2 补齐另两个维度:「就业行情」(AI agent 相关岗位市场)和「行业动态」(公司 / 产品 / 融资 / 开源动向)。用户无外部搜索 API key,采用轻量方案。

## 2. 目标

让 agent 用现有 GLM 内置 `web_search` 主动覆盖就业 / 行业问题,并按结构化模板输出(就业行情卡 / 行业动态简报),数据定性近似、附来源与时效。

## 3. 方案(轻量 A2)

- 扩展 `SYSTEM_PROMPT`:加就业 / 行业调研指引
- 新增两个模板常量:`JOB_CARD_TEMPLATE`、`INDUSTRY_BRIEF_TEMPLATE`,`SYSTEM_PROMPT` 引用
- 自动识别问题类型套模板(不加斜杠命令)
- 不加工具、不加 key、不改架构、不动其他文件

## 4. 改动范围

仅 `agent_radar/agent/loop.py`:
- 扩展 `SYSTEM_PROMPT`(就业 / 行业指引 + 引用模板)
- 新增 `JOB_CARD_TEMPLATE`、`INDUSTRY_BRIEF_TEMPLATE` 模块常量

## 5. 模板字段

**就业行情卡** `JOB_CARD_TEMPLATE`:
岗位方向 / 薪资区间(定性,标注"近似 / 公开数据") / 核心技能 Top5 / 热门城市 / 需求趋势(一句话) / 来源 + 时效

**行业动态简报** `INDUSTRY_BRIEF_TEMPLATE`:
近期重要动态(融资 / 新品 / 开源) / 值得关注的公司·项目 / 趋势判断(升温 / 降温) / 来源 + 时效

## 6. 约束

- 就业数据**定性近似**,不编造精确数字,标注"近似 / 公开数据"
- **不爬**招聘站(BOSS / 拉勾)
- 附来源链接 + 说明时效
- 用简体中文

## 7. 触发

**自动识别**:agent 据问题套对应模板;混合问题综合输出。无命令、无特殊路由。

## 8. 测试

- 断言 `SYSTEM_PROMPT` 含就业 / 行业指引关键词(如"就业"、"行业动态")
- 断言 `JOB_CARD_TEMPLATE` / `INDUSTRY_BRIEF_TEMPLATE` 存在,且含必填标记(如"来源"、"时效"、"近似")
- 真实效果靠手动 smoke test(需 GLM key)

## 9. 非目标(YAGNI)

- 不加 `jobs_search` / `news_search` 工具(需外部搜索 key,属"中等"方案,未来可选)
- 不加 `/jobs` `/news` 斜杠命令(用户选自动识别)
- 不接真实招聘数据源(反爬 / 法律风险)
