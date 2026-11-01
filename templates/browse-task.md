# 任务书模板 v3 · Deeplurk 平台浏览（三步判定版）

> 用法：`{...}` 为占位符，由主控填写。整段交给本地 OpenClaw agent。
> 依据：`x-science-browse-task.md` + `OpenClaw_Agent编排与运维经验.md`。

---

# 任务：浏览 {PLATFORM} 的 {COMMUNITY}，只记录「自身知识与网络检索都解决不了」的问题

你是本机 OpenClaw（2026.9.33）里的 agent，会话键 `agent:{AGENT_ID}:{TASK_ID}-r{ROUND}`。
浏览器 profile 强制：**`{PROFILE}`**（不要串用其他 profile）。

## 1. 做什么

**自由浏览 {COMMUNITY}**，不是按清单点名，而是顺着信息流/搜索走：

- 入口：{ENTRY_URL}
- 可用检索：{SEARCH_URLS}
- 关键词从领域出发：{KEYWORDS}
- 看到有价值的帖子可顺着引用、回复、作者页继续走；允许"随意刷"，不要求线性覆盖

**核心产出不是"收集帖子"，而是记录问题**：那些**你自己的知识回答不了、网络检索也补不齐**的问题。

## 2. 三步判定（每个候选问题都必须走完）

**第 1 步 · 自身知识**
能给出可靠、可辩护的答案（含「公认结论 / 已知开放问题 / 概念错误」）→ 跳过，记 `resolved_by_self_knowledge` + 理由。

**第 2 步 · 网络检索**（必须真的打开检索页）
- 白名单引擎：{SEARCH_ALLOWLIST}
- 检索词具体化：关键概念 / 论文标题作者 DOI / 争议双方说法
- 记录**实际检索词**与结果要点
- 有明确答案或权威文献 → 跳过，记 `resolved_by_web_search`

**第 3 步 · 仍解决不了 → 记录**，并写清卡在哪。

## 3. 记录字段（`{OUT_DIR}/problems.jsonl`，一行一条）

字段见系统提示词第二节。必须包含：`post_url`（真实永久链接，实际打开过）、`post_read`、
逐字 `excerpt`、`why_unresolved`、`self_knowledge_assessment`、`web_search_attempts[]`、
`search_coverage_note`、`what_would_resolve`、`confidence_unresolved`、`dedupe_group`。

## 4. 其余产物

- `ledger.jsonl`：每次浏览/检索一行
  `{"record_type":"access","request_id":"","timestamp_utc":"","action":"open_post|web_search|open_paper","target_url":"","result_status":"ok|blocked|failed","verdict":"candidate|resolved_by_self_knowledge|resolved_by_web_search|skipped_irrelevant|recorded"}`
- `heartbeat.jsonl`：每记录一条/每轮结束一行；本轮收尾写 `kind:"turn_end"`
- `files-index.md`：分片登记（文件名/行数/首末时间/覆盖）

## 5. 写盘纪律（违反即本轮作废）

- **只追加**：use a safe append-only local writer，禁止 `read` 全文 + `write` 写回
- **UTF-8 无 BOM**；use an append writer that explicitly selects UTF-8
- 单文件 > 40 KB 滚到 `.partN`
- 写完自检：a locally reviewed JSONL validator

## 6. 边界（违反即停止本轮）

- 只读：不发帖、不点赞、不评论、不转发、不关注、不私信、不投票
- 不读取/导出/传递 cookie、密码、令牌；登录与验证码由用户处理
- 只走 OpenClaw browser 工具；遇验证码/登录页/403/限流/策略拒绝：**立即停止该项并如实记录**，不绕行
- 网络检索只用白名单引擎；连续 3 次被拒 → `kind:"stop"`
- 标签卫生：每帖/每次检索用新标签，读完立即关
- 不生成、不补足、不编造任何帖子、链接、时间、摘录、检索词或检索结果

## 7. 判定硬规则

1. 「解决不了」不是「懒得查」；台账要能看到真实检索词
2. 不得从标题推断内容；`post_read=false` 不得记录
3. 检索结果不得美化；`contradictory` 要能说清矛盾双方
4. 不宣称新颖性；`novelty_status` 恒 `unknown`
5. 帖子声称 / 检索内容 / 自己推理，三者不得混
6. 失败与受限必须记录

## 8. 预算与收尾

- 单轮：**{TURN_MINUTES} 分钟**或完成 **{N_JUDGEMENTS} 次完整三步判定**，先到为准
- 正常收尾写 `kind:"turn_end"` 并更新索引
- 续跑先读既有产物，不重置 `problem_id`，不重复记录 `post_id`
- 收尾中文汇报：浏览帖数、检索次数、记录问题数、跳过数、累计、阻塞

## 9. supervisor 参数（由主控填写，不写进 agent 任务书）

```yaml
answer_attempt_required: true       # 无作答记录的候选判 INVALID
min_confidence_to_discard: medium   # 多确定才算已答出
search_budget_per_problem: 3        # 每题最多检索次数
keep_if_unresolved: [knowledge, search]
record_discarded: true              # 被丢弃的也要落盘（可审计）
turn_minutes: {TURN_MINUTES}
max_turns: {MAX_TURNS}
```
