# 新手审图工程师第一小时 Playbook

本文件面向第一次接触 ArchReview-KG 的审图工程师。它解释如何从一个 run 目录快速判断“该先看什么、哪些证据可信、哪些问题需要人工复核”。

## 先跑一个完整审图

```bash
archkg review samples/sample_clean.pdf -o out/review-demo \
  --project-meta samples/project_meta_demo.yaml \
  --room-schedule samples/room_schedule_demo.yaml \
  --stair-schedule samples/stair_schedule_demo.yaml

archkg viewer -o out/review-demo --source samples/sample_clean.pdf
```

每次完整审图都会生成两个新手入口：

- `reviewer_onboarding.json`: 机器可读的第一小时流程、常用命令和边界提醒。
- `reviewer_quickstart.md`: 可直接交给审图工程师阅读的上手清单。
- `sheet_issue_review_queue.json`: per-sheet preview 的有界人工审阅队列，供逐页核对。

如果要把本次 run 交给另一位工程师，只复制只读交接包：

```bash
archkg handoff-package out/review-demo -o out/review-demo-handoff
archkg handoff-check out/review-demo-handoff
archkg handoff-signoff out/review-demo-handoff \
  --reviewer reviewer-name \
  --status needs_info \
  --note "缺少剖面净高证据"
```

交接包包含 `handoff_manifest.json`、`handoff_summary.md` 和 `artifacts/` 复制件；它不修改原 run。
交接前应让 `handoff-check` 输出 `handoff_ready`。
交接复核人可用 `handoff-signoff` 写入 `reviewer_signoff.json` / `.md`，状态只能是 `ready`、`needs_info` 或
`blocked`；该记录只是包内交接备注，不确认 issue，也不是合规证书。

## 第一小时流程

1. 打开 Viewer，先看“新手上手”和“审图工作台总览”。
2. 核对 source preview、entity overlay、annotated PDF，确认识别没有明显错位。
3. 看 `drawing_understanding.json` 的图纸类型、房间、门、走廊、楼梯、尺寸数量。
4. 看 `rule_input_readiness.json`，把 missing input 和 low confidence 列为待补证据。
5. 看 Sheet 分类、路由、候选区域和 `sheet_issue_review_queue.json`，确认系统读的是正确设计区。
6. 逐条复核 `issues.json` candidate issue；不要把 candidate 当 confirmed。
7. 用 `archkg review-state` 写入 confirmed / rejected / needs_info。
8. 交接时附上 run 目录、已确认事项、待补输入、低置信证据和未处理页面。

## 必守边界

- 缺输入不等于通过。
- `issues.json` 是 candidate 输出，人工确认前不是最终违规。
- `sheet_issue_review_queue.json` / `sheet_issues.json` 是 per-sheet preview，不会自动进入主 `issues.json` 或 `review_state.json`。
- 不要把 `sheet_issue_review_queue.json` 的 `preview_id` 传给 `archkg review-state`；该命令只处理主 `issues.json` 的 issue id。
- `evidence_ready` 只适用于已 benchmark 的图纸类别，不是任意复杂真实图纸自动审批证明。
- OCR、VLM、text_hint 都只能辅助复核，不能替代条文和实体证据链。

## 常用命令

```bash
# 打开结果页
archkg viewer -o out/review-demo --source samples/sample_clean.pdf

# 确认单条主 issue
archkg review-state out/review-demo <issue_id> \
  --status confirmed \
  --reviewer reviewer-name \
  --note "图面和条文均已核对"

# 发现证据不足
archkg review-state out/review-demo <issue_id> \
  --status needs_info \
  --reviewer reviewer-name \
  --note "缺少剖面净高或门类型输入"

# 修图或补数据后对比两次 run
archkg review-diff out/review-before out/review-after \
  -o out/review-after/review_diff.json

# 演示或交付前跑 readiness gate
archkg release-readiness \
  --manifest samples/understanding_benchmarks/suite_manifest.json \
  --run-dir out/review-demo \
  --out out/review-demo/release_readiness.json \
  --markdown out/review-demo/release_readiness.md

# 生成只读交接包
archkg handoff-package out/review-demo -o out/review-demo-handoff

# 检查交接包完整性
archkg handoff-check out/review-demo-handoff \
  --out out/review-demo-handoff/handoff_quality.json \
  --markdown out/review-demo-handoff/handoff_quality.md

# 写入交接复核备注
archkg handoff-signoff out/review-demo-handoff \
  --reviewer reviewer-name \
  --status needs_info \
  --note "缺少剖面净高证据" \
  --blocker "missing section height" \
  --needs-info "door type schedule" \
  --next-action "request section sheet"
```

## 交接模板

```text
结论：
阻塞：
已确认 issue：
已驳回 issue：
needs_info：
缺失输入：
低置信证据：
未进入主生命周期的 preview：
run_dir：
commit：
验证命令：
handoff_package：
handoff_quality：
reviewer_signoff：
下一步：
```
