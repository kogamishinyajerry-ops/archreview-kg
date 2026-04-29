# ArchReview-KG

> 民建图纸自动审图引擎 — 32 张 GB 国标规则卡 + 实体图谱构建器 + 对抗训练 lane

[![pytest](https://img.shields.io/badge/pytest-423%20passing-brightgreen)](#)
[![rules](https://img.shields.io/badge/rules-32%2F32%20covered-brightgreen)](#)
[![adversarial](https://img.shields.io/badge/F1-1.00%20on%20100--case%20battery-brightgreen)](#)
[![version](https://img.shields.io/badge/version-1.2.1-blue)](CHANGELOG.md)

ArchReview-KG 把上传的 PDF 平面图自动转成实体图谱（房间 / 户门 / 走廊 / 尺寸标注），
对照 30 条国标规则（GB 50096 / 50352 / 50016 / 50763）逐条评估，输出标注 PDF
+ 复核报告 + 问题清单 JSON。

> ⚠️ **当前定位**: 评估阶段工具，不是即开即用的生产服务。详见 [READINESS.md](READINESS.md)。
> 4 / 32 张规则可在任意 PDF 上直接判违规 (AUTODETECTABLE)；其余规则需要用户填
> ProjectMeta / 房间排表 / 楼梯排表 YAML 才能完整触发。

---

## 30 秒看演示

```bash
git clone https://github.com/kogamishinyajerry-ops/archreview-kg.git
cd archreview-kg
uv pip install -e .

# 选 1: 浏览器拖拽上传 (推荐第一次用)
archkg studio
# → 自动打开 http://127.0.0.1:8765, 直接拖 PDF 或点 "跑内置 demo" 看效果

# 选 2: CLI 一键 demo
archkg demo --meta --room-schedule --stair-schedule
archkg viewer -o out --source samples/sample_clean.pdf
```

`out/` 下会有：
- `annotated.pdf` — 标注红框 + 文字说明的 PDF
- `report.md` — 中文复核报告（违规清单 + 人工核对提醒分区）
- `reviewer_quickstart.md` — 新手审图工程师第一小时上手清单
- `issues.json` — 结构化问题清单（rule_id / bbox / severity / 证据）
- `review_state.json` — 人工复核状态层（candidate / confirmed / rejected / needs_info / resolved / superseded），不回写 `issues.json`
- `review_diff.json` — 两次 run 的主 `issues.json` 差异追踪（unchanged / changed / new / resolved），由 `archkg review-diff` 生成；Viewer/Studio 会显示，但不回写任一 run
- `release_readiness.json` — 基于 benchmark suite 与代表性 run artifacts 的发布/演示成熟度门禁；由 `archkg release-readiness` 生成，不以规则数量作为成熟度证明
- `review_workbench.json` — 审图工作台总览，汇总图纸理解、规则输入就绪度、sheet 证据、候选问题和复核状态；提供 evidence 跳转与受限 review-state 操作模板，不改变规则结论
- `entity_graph.json` — 抽出的实体图谱
- `drawing_understanding.json` — 图纸理解摘要（图纸类型 / 可能设计对象 / typed component inventory / 空间、洞口、通行、尺寸证据清单）
- `sheet_graphs.json` — 每个高置信 plan sheet 的独立 graph 证据输出；P39-01 不把多 plan 页合并进主规则结论
- `sheet_issues.json` — 每个 plan sheet 的候选问题 preview；P39-02 不写入主 `issues.json` / `review_state.json`
- `layout_3d.json` / `layout_3d_summary.md` / `layout_3d.glb` — 从 graph 证据生成的 2.5D 布局模型；只用于空间理解和复核导航，默认高度/厚度均写入 assumptions；P72 起显式 `Door.width_m` / `Door.properties.height_m` 等会记录为 opening measurement provenance，但仍不作为 BIM 真值或合规判断
- `layout.ifc` / `layout_ifc_export.json` / `layout_ifc_export.md` — 可选显式导出的 IFC preview；只从 `layout_3d.json` 派生，不随默认审图自动生成，不作为审查级 BIM 或规范判断输入
- `sheet_issue_review_queue.json` — 从 per-sheet preview 派生的有界人工审阅队列；preview id 不能用于 `archkg review-state`
- `rule_input_readiness.json` — 每张规则卡在本次 run 中的输入就绪度（ready / missing_input / low_confidence / manual_only / not_applicable / unsupported_entity）
- `sheet_classification.json` — 多页图纸 sheet 类型分类（plan / schedule / title / legend / detail / elevation / unknown），只做路由证据，不自动跳页
- `sheet_routing.json` — 受保护 graph 路由决策；只有高置信单一 plan 页场景才过滤非 graph 页，否则回退 legacy 全页输入
- `sheet_region_candidates.json` — 设计区 / 标题栏 / 排表 / 图例的候选区域和候选排除文本摘要（只建议，不自动裁剪）
- `sheet_region_candidates_overlay.png` — 候选区域框线预览图，便于复制 region 前人工确认
- `reviewer_task_sequence.json` / `.md` — 新手 reviewer 的按优先级任务序列（只排序 evidence，不确认 issue）
- `index.html` — viewer 渲染的查阅页

如需交给另一位审图工程师复核，可生成只读交接包：

```bash
archkg handoff-package out/ -o out-handoff
archkg handoff-check out-handoff --out out-handoff/handoff_quality.json --markdown out-handoff/handoff_quality.md
archkg handoff-signoff out-handoff --reviewer reviewer-name --status needs_info --note "缺少剖面净高证据"
archkg handoff-checklist-update out-handoff --ordinal 1 --reviewer reviewer-name --status done --note "已核对交接边界" --evidence-checked handoff_manifest.json
archkg handoff-ready-runbook out-handoff
archkg handoff-manager-checklist out-handoff --manager manager-name --note "等待补齐剖面证据"
archkg handoff-archive-manifest out-handoff --created-by manager-name --note "移交前固化 checksum"
archkg handoff-archive-verify out-handoff
open out-handoff/index.html

# 多个交接包放在同一目录时，生成负责人批量索引
archkg handoff-bundle-index handoff-packages/
open handoff-packages/handoff_bundle_index.html
```

`out-handoff/` 会包含 `index.html`、`handoff_manifest.json`、`handoff_summary.md` 和 `artifacts/` 复制件；
它只复制证据，不写回原 run，不确认 issue，也不把 per-sheet preview 升级为主违规。
`handoff-check` 会独立检查 manifest schema、只读策略、必需 artifact、复制件存在性和边界提醒。
`handoff-signoff` 只在交接包内写 `reviewer_signoff.json` / `.md`，用于记录 ready / needs_info / blocked
状态、阻塞项和下一步；它不是合规证书，也不回写源 run。
`handoff-manager-checklist` 只在交接包内写 manager checklist，用于负责人快速判断包能否进入下一轮复核；
P65 起它会读取包内 reviewer checklist，只有清单完成时才允许 `manager_ready`。
`handoff-archive-manifest` 只在交接包内写 checksum 清单，用于移交完整性核对，不是合规证书。
`handoff-archive-verify` 只对照 checksum 清单检查包内文件是否缺失、变更或多出，发现 drift 时返回非零。
`index.html` 是静态只读入口，会汇总 package boundary、quality、signoff、manager checklist、archive manifest、verification 和 artifact 链接。
`handoff-bundle-index` 会在多个 package 的父目录写 `handoff_bundle_index.json` / `.md` / `.html`，
用于负责人快速筛选 ready / needs_info / blocked 包；它不写入任何单包目录，也不是合规证书。
P61 起交接包也会携带 `reviewer_task_sequence.json` / `.md`，让接手 reviewer 先处理
readiness blockers，再看主 issue，最后看 per-sheet preview 和 handoff 动作。
P62 起每次完整 run 还会生成 `reviewer_task_checklist.json` / `.md`，把任务序列转成
可人工填写的复核清单；它只帮助记录证据和风险，不会自动确认 issue 或写回 review state。
P63 起 `handoff-bundle-index` 会汇总每个包内 checklist 的 open item 数和
`checklist_review_status`，方便负责人跨包看复核工作量；它不修改单包，也不改变 package readiness。
P64 起 reviewer 可用 `archkg handoff-checklist-update` 在交接包内更新单个 checklist item，
记录 reviewer_status、note 和 evidence_checked；它只写 package-local 文件，不碰源 run。
P65 起 manager checklist 会把 reviewer checklist completion 纳入 intake：open / needs_info 行会让
manager 状态停在 `manager_needs_info`，blocked 或缺失清单会阻塞；这仍只是交接状态，不是合规结论。
P66 起交接包会生成 `handoff_ready_runbook.json` / `.md`，并可用 `archkg handoff-ready-runbook`
刷新；它把 quality、signoff、checklist、manager gate 汇成新手下一步命令，不写源 run。
P67 起 `handoff-bundle-index` 会为每个包标出 `next_actor` 和下一动作命令，
让负责人跨包看到当前应由 reviewer、manager 还是 archive 继续处理。
P68 起完整 review run 会生成 `layout_3d.json`、`layout_3d_summary.md` 和 `layout_3d.glb`，
帮助 reviewer 从平面图 graph 证据理解房间、墙段、门洞、楼梯占位和尺寸锚点的 2.5D 空间关系；
这不是 IFC/BIM 输出，也不会改变规则引擎结论。
P69 起可显式运行 `archkg ifc export-layout` 把 `layout_3d.json` 导出为 `layout.ifc` preview；
该命令需要可选 IfcOpenShell 依赖，缺依赖时写出 `dependency_missing` 报告并返回非零，
不会影响普通 PDF/栅格审图流水线。

---

## 真实图纸 — 浏览器路径（推荐）

```bash
archkg studio
```

打开后:
1. **拖** PDF 平面图到上方框
2. 展开 "ProjectMeta YAML" / "房间排表 YAML" / "楼梯排表 YAML" 区块, 选填本项目的 YAML（不填也能跑, 只触发 4 张直判规则）
3. 点 "▶ 跑审图"

完成后页面跳转到结果视图: 左侧标注 PDF 预览 / 右侧问题清单 + 复核报告。
点 "没图纸？跑内置 demo" 用 `samples/sample_clean.pdf` 看完整流程。

## IFC/IDS Side Lane（可选）

```bash
archkg ifc validate --ifc model.ifc --ids requirements.ids -o out/ifc

# P69: 从 graph-derived 2.5D evidence 显式导出 IFC preview
archkg ifc export-layout \
  --layout out/layout_3d.json \
  --out out/layout.ifc \
  --report out/layout_ifc_export.json \
  --markdown out/layout_ifc_export.md

# P70: 安装后运行真实 IFC smoke（可选）
pip install ifcopenshell
archkg ifc export-layout \
  --layout out/layout_3d.json \
  --out out/layout.ifc \
  --report out/layout_ifc_export.json \
  --markdown out/layout_ifc_export.md
```

该路径独立于 PDF 图纸识别流水线。安装 IfcOpenShell/IfcTester 后，`validate` 会写出
`ids_report_raw.json`、`ifc_validation.json` 和 `ifc_issues.json`；安装 IfcOpenShell 后，
`export-layout` 会把 `floor_slab`、`wall`、`room/corridor volume`、`door_opening`
和 `stair_placeholder`、`window_opening` 映射成基础 IFC preview 实体。缺少可选依赖时 CLI 会清晰降级提示，
并在传入 `--report/--markdown` 时仍写 `layout_ifc_export.v1` 报告。`layout.ifc` 不是审查级 BIM，
不读取 PDF，不改变 `issues.json` / `review_state.json` / 规则引擎结论。

P70 还要求在 `layout_3d` 中将明确窗口洞口（例如 `Door` 上有 `opening_kind: "window"` 或
`is_window: true`）建模为 `window_opening`，并导出为 `IfcWindow`。这是一层轻量、可回退的
graph-backed 语义增强；没有明确证据时仍保持 door placeholder，不会改变默认规则语义。
P71 起 `layout_3d_summary.md` 和 Viewer/Studio 会显示 `Opening Semantics`，
并在 opening object 的 `properties.opening_semantic` 中记录语义来源；它只帮助 reviewer
审计 door/window opening 来源，不改变规则输出或 IFC preview 边界。
P72 起 opening object 还会在有明确 graph 字段时记录 `properties.opening_measurement`：
`Door.width_m`、`Door.properties.height_m`、`sill_height_m`、`head_height_m` 会带上来源和单位。
缺失字段继续走显式 assumptions；这些尺寸只用于 3D preview 复核导航，不进入规则引擎。

## Rule-Card Draft Authoring

```bash
archkg rule-card draft --clause-id GB50096-5.7.2 -o out/rule_card_draft.json
```

该命令只生成 `rule_card_draft.v1` 草稿 artifact，记录源条文、阈值、建议输入、适用性、模糊点和 proposed tests。草稿状态固定为 `draft`；人工确认前不会写入 active `rule_cards.yaml`，也不会生成最终审图 issue。

## 3 步可视化上手（Studio / 本地优先）

- 第 1 步：`archkg studio` 打开后，拖入 PDF / PNG / JPG。
- 第 2 步：默认参数先跑一遍，`inspect_only` 适合先验实图面是否可读。
- 第 3 步：结果页按三层看：
  - **图层对照**：`source / entity overlay / annotated` 三种图层快速切换
  - **问题面板**：先看 `高风险` 与 `热点规则` 再展开明细
  - **条文地图**：点击 `条文触达地图` 与 `report.md` 做复核闭环

> ⚠️ **真实 CAD 图纸提示** (v1.2.1 起): 第一次跑陌生 PDF 时, 展开 "⚙️ 高级参数" 选 **"🔍 仅识图模式"** —
> 只跑实体提取, 跳过规则评估。如果 builder 检出 rooms / doors 数字看起来合理 (一户型 ~5-10 rooms), 再用完整模式让规则跑;
> 如果数字异常 (例如 169 rooms), 顶部红色质量标记会提示 builder 在 over-segmenting, 这时规则报告里的违规多数是假阳性。
>
> v1.2.2 起表单还有 **`min_room_area_m2`** 字段 (默认 1.0 m²) 在 builder 层过滤亚阈值的噪声多边形。
> **已知限制**: 噪声过滤假设墙是零厚度线段。Synthetic 样例和很多 metric CAD 导出符合此假设, 但具体能否 work
> 取决于你的 CAD 导出方式, 我们没在足够多真实图纸上验证。
> **症状判断**: 如果结果里 door 数量异常少 (例如 0 或显著少于实际户数), 优先怀疑是双线墙问题。
> **诊断**: 把 `min_room_area_m2` 设为 `0` 再跑一次, 如果 door 数量恢复, 基本可以确认是双线墙触发了过激过滤。
> **应对**: 在 CAD 里把双线墙合并为单线再导出, 或等 v1.3+ 处理。
>
> **栅格 OCR beta**: PNG/JPEG 上传默认不跑 OCR；如本机已安装 `.[ocr]` 可在 Studio 识图参数里勾选
> "栅格 OCR beta"。OCR 成功返回文本时会写入 `primitives.json` 并参与房间标签绑定；
> 结果页会显示 OCR 证据面（文本、置信度、绑定房间、低置信度提示），并把 label 冲突、
> 未绑定高置信度 label、低置信度 label 标为人工 QA 候选。QA 候选不会自动改 Room.label，
> 也不会改变规则结论。OCR 数字文本还会显示 Door/Corridor 尺寸绑定证据，说明 OCR 值绑定到了哪个实体；
> 这只是证据展示，不是单独的合规结论。OCR 不可用或无结果时仍按 partial 审图降级，
> 并明确提示 5 张 label-dependent Room 规则不会触发。
>
> **图纸理解摘要**: 每次结果页会生成 `drawing_understanding.json` 并显示 "图纸理解摘要" 面板，
> 汇总当前识别出的图纸类型、可能设计对象、空间/门洞/通行部件与尺寸证据。这个面板的目标是先回答
> "这张图在设计什么、有哪些部件、尺寸证据绑定到了哪里"；它不会把 QA 候选或 OCR 尺寸直接升级为规范违规结论。
> v1.4-dev P24 起，摘要还包含 `component_inventory`、`drawing_profile` 和 `benchmark_signals`：
> 楼梯/垂直交通会进入 typed inventory，识别档案会显式列出 spatial layout / openings /
> circulation / dimensions / OCR text 等证据信号，便于后续真实图纸 benchmark 横向比较。
>
> **规则输入就绪度**: 完整审图模式会额外生成 `rule_input_readiness.json`，逐张规则卡说明本次 evidence
> 是否足够运行：`ready`、`missing_input`、`low_confidence`、`manual_only`、`not_applicable` 或
> `unsupported_entity`。它不改变 `issues.json`，只解释哪些规则缺项目字段、缺实体输入、只适合作为人工提醒，
> 或因 ProjectMeta 适用性被跳过。结果页和 `report.md` 会显示同一份摘要，明确提示“缺输入不等于通过”。
>
> **Sheet 分类**: 完整审图会生成 `sheet_classification.json`，逐页标记 `plan`、`schedule`、`title`、
> `legend`、`detail`、`elevation` 或 `unknown`，并说明是否适合进入 graph。完整审图还会生成
> `sheet_routing.json`：只有“多页、恰好一个高置信 plan、其余页都是高置信非 graph 类型”时，
> 才把 graph 输入收窄到该 plan 页；unknown、低置信或多个 plan 页会回退 legacy 全页输入。
> 另会生成 `sheet_graphs.json`，对每个高置信 plan sheet 独立 build graph，作为多页图纸理解证据；
> P39-01 不把这些 per-sheet graph 自动合并成最终违规结论。P39-02 起还会生成
> `sheet_issues.json`，按 sheet graph 运行规则得到候选问题 preview；它不写入主 `issues.json`
> 或 `review_state.json`，避免多页候选和人工复核状态混在一起。
> P47 起还会生成 `sheet_issue_review_queue.json`，把 preview rows 收束成
> `preview-only bounded bridge`，方便新手逐页核对；这些 `preview_id` 不是主 issue id，
> 不能传给 `archkg review-state`，也不会自动合并进主生命周期。
>
> **候选区域**: 完整审图会生成 `sheet_region_candidates.json`，提示可能的 `design_region`、`title_block`、
> `schedule`、`legend` 和候选排除文本。它不会自动修改 `primitives.json` 或 `entity_graph.json`；
> 只有用户显式传 `--sheet-region x0,y0,x1,y1` 时才会真正裁剪。结果页还会显示
> `sheet_region_candidates_overlay.png`，用彩色框线帮助人工确认候选区域。
>
> **审图工作台总览**: 完整审图会生成 `review_workbench.json`，把 `drawing_understanding.json`、
> `rule_input_readiness.json`、Sheet 分类/路由/graphs/issues、`issues.json` 和 `review_state.json`
> 汇总成一个入口面板，并提供跳转到图层、component inventory、readiness blockers、sheet evidence、
> candidate issues、review state 和 report 的 action links。它只帮助 reviewer 判断先看哪里、缺什么、哪些仍是 candidate；
> `archkg review-state` 可受限更新主 `issues.json` 对应的 `review_state.json`，不会修改 `issues.json`、per-sheet preview issues 或规则引擎结论。
> Viewer/Studio 还会按 `page_index` 映射主 issue bbox，并生成 `preview_pages.json`：
> source / annotated 预览支持多页切换，非第一页 issue 可直接切到对应页并高亮 bbox；
> entity overlay 也会为 graph-backed 图纸页生成多页预览；没有 graph 的页仍需看 source/annotated/PDF。
>
> **Re-run diff**: 修图后重跑审图，可用
> `archkg review-diff out/run-before out/run-after -o out/run-after/review_diff.json`
> 比较两次主 `issues.json`。匹配不会依赖每次运行随机生成的 `issue_id` 或 entity IDs，而是使用规则卡、条文、页码、空间排序和证据指纹；
> 输出只标记 `unchanged`、`changed`、`new`、`resolved`。Viewer/Studio 会在工作台和 issue 行显示这些状态，但不会自动修改
> `review_state.json` 或把 per-sheet preview issue 升级为主问题。
>
> **新手审图上手包**: P46 起完整审图会生成 `reviewer_onboarding.json` 与
> `reviewer_quickstart.md`，把 source/overlay 核对、component inventory、readiness blockers、
> sheet scope、candidate issues、review-state 操作和交接检查组织成“第一小时流程”。它只是 reviewer
> guidance，不确认 issue、不修改规则输出，也不扩大合规宣称。
>
> **Release readiness gate**: 对外演示或发布前，可运行
> `archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir out/ --out out/release_readiness.json --markdown out/release_readiness.md`
> 生成门禁报告。当前门禁把 active benchmark suite、至少一张 active 真实图纸、核心 run artifacts
> 和可选成熟度 artifacts 作为证据；`known_gap`、`pending_fixture` 和 generated-heavy proof 会阻止
> `evidence_ready` 宣称。P45 后 packaged suite 可在代表性 run artifacts 完整时进入
> `evidence_ready`，但只适用于已 benchmark 的图纸类别，不证明任意复杂真实图纸已可自动合规审查。

YAML 模板和填法见 `samples/` 目录或下面 CLI 流程。

---

## 真实图纸 — CLI 三步走

```bash
# 1. 准备 ProjectMeta YAML（住宅类型、层数、户数、耐火等级）
cp samples/project_meta_demo.yaml meta.yaml
# 编辑 meta.yaml 填入实际项目数据

# 2. 准备房间排表 YAML（净高 / 楼层 / 坡屋顶 等剖面信息）
cp samples/room_schedule_demo.yaml rooms.yaml
# 按图纸所标房间逐条填入；selector 用 room_id 或 label 匹配

# 3. 跑审图
archkg review your-plan.pdf -o out/ \
  --project-meta meta.yaml \
  --room-schedule rooms.yaml \
  --stair-schedule stairs.yaml   # 可选：楼梯踏步/踢面/扶手等

archkg viewer -o out/ --source your-plan.pdf

# 可选：对“识别到了什么”跑 benchmark（不评估规范纠错）
archkg understanding-benchmark out/ \
  --expect samples/understanding_benchmarks/sample_clean_full.json \
  --out out/understanding_benchmark.json \
  --markdown out/understanding_benchmark.md

# 可选：从当前识别结果生成 expected spec 草案（先人工核对，再把真实图纸升为 active case）
archkg understanding-benchmark-author out/ \
  --benchmark-id my-real-plan \
  --out out/expected_understanding.draft.json

# 可选：跑 benchmark suite intake（known_gap 会真实跑分，但不算能力通过）
archkg understanding-benchmark-suite \
  --manifest samples/understanding_benchmarks/suite_manifest.json \
  --out out/understanding_benchmark_suite.json \
  --markdown out/understanding_benchmark_suite.md

# 可选：对当前 run 做发布/演示成熟度门禁
archkg release-readiness \
  --manifest samples/understanding_benchmarks/suite_manifest.json \
  --run-dir out/ \
  --out out/release_readiness.json \
  --markdown out/release_readiness.md

# 新手审图工程师第一小时 runbook
open docs/reviewer/novice-reviewer-playbook.md
```

P40 起，expected spec 也可以检查多页套图证据：`sheet_graphs.graph_count`、per-sheet component counts、
`sheet_issues.sheet_count`、per-sheet required rule ids。Packaged suite 已包含 deterministic
`generated-multi-plan-sheets` active case，用来锁定 `sheet_graphs.json` 与 `sheet_issues.json`。
真实 Medfield 9 页 plan/elevation set 曾作为 `known_gap` 接入，用来暴露 primary full-set
understanding 的 openings 缺口。P44 起，`drawing_understanding.json` 会把 `sheet_graphs.json`
的多页 plan graph 计数作为
识图证据汇总到 full-set 摘要中。Medfield 9 页 plan/elevation set 已从 `known_gap` 晋升为
active recognition benchmark；这只证明多页识图 evidence 已可追踪，不代表 per-sheet preview
issues 已进入主 `issues.json` 或自动合规聚合。
P55 起，suite 又新增 Medfield A-2 Second Floor Plan 真实单页 expected inventory，以及
deterministic generated mixed-sheet-set benchmark。Packaged suite 当前为 active=7、pending=0、
known_gap=0，且 real_active=3、generated_active=3。这个变化扩大的是识图回归面，不把生成图纸
或单一公共项目当作任意真实复杂图纸证明。

不填 `--project-meta` 也可跑，但只能触发 4 张 AUTODETECTABLE 规则
（户门净宽 / 走廊净宽 / 卧室面积 / 无障碍走廊）；其它项目级规则会被
applicability filter 跳过并在报告里说明原因。

---

## 这个引擎能查什么

按当前 v1.1 能力分级 (`archkg clause readiness`)：

| Tier | 数量 | 含义 | 例子 |
|---|---|---|---|
| **AUTODETECTABLE** | 4 | 上传图纸即可自动判违规 | 户门净宽 < 0.90 m / 走廊净宽 < 1.20 m / 卧室面积 < 5.0 m² |
| **PROJECT_META_DRIVEN** | 1 | 用户填 ProjectMeta 即可自动判 | 无障碍住房比例 < 2/100 |
| **PARTIAL_AUTODETECT** | 4 | 加房间排表 YAML 后可判 | 卧室净高 < 2.40 / 卧室在地下室 / 坡屋顶净高 |
| **STAIR_PENDING** | 5 | 加楼梯排表 YAML 后可判 | 楼梯踏步 < 0.26 / 踢面 > 0.175 / 扶手 < 0.90 |
| **HIGH_RISE_PROJECT** | 5 | 项目高度 / 层数自动触发 | 7层以上无障碍设计 / 100m 以上避难层 / 33m 以上防烟楼梯 |
| **EVAC_STAIR_BANDS** | 3 | 项目高度自动触发 | 21-33m 区间封闭楼梯间 / 一二级耐火 + 低多层户门疏散距离 |
| **REMINDER_BY_DESIGN** | 18 | severity=info 人工核对清单 | "项目为住宅，请核对外窗窗台 < 0.90m 时是否设防护设施" |

**可触发的规则总数（v1.1）**: 22 张 (4 + 1 + 4 + 5 + 5 + 3) + 18 张人工核对提醒。

---

## 对抗训练 lane (v1.0.4 - v1.0.9 新增)

```bash
# 跑 100-case deterministic 对抗 battery
archkg adversarial run -n 100 --seed 5000 -o tmp/battery
# → 985 TP / 0 FN / 0 FP across 21 targeted rules at F1=1.00

# 1000-seed 纯 predictor sweep, 审计每条 rule 的 case rate / 触发负载
archkg adversarial sample-stats -n 1000 --seed 5000
```

这条 lane 在过去 6 个 patch ships 里发现并修复了两个真 bug（builder polygonize
snap mismatch / examiner height_class 分类错误），并在 v1.0.9 升级成自审计
infrastructure：每条 targeted rule 必须 ≥ 5% case rate，否则测试 fail。

详见 [CHANGELOG.md](CHANGELOG.md) v1.1.0 entry。

---

## 安装

```bash
# 推荐 uv（快）
uv pip install -e .

# 或者 pip
python -m pip install -e .

# 开发依赖
uv pip install -e ".[dev]"  # pytest, ruff, mypy
```

依赖：Python 3.11+ / Pydantic 2 / shapely / PyMuPDF / typer / Jinja2 / trimesh。可选
OCR 功能依赖 PaddleOCR (`uv pip install -e ".[ocr]"`)。

---

## 仓库结构

```
archkg/
  ingest/           PDF 解析 → primitives.json (lines + texts)
  graph/            primitives → EntityGraph (rooms / doors / corridors / dimensions / stairs)
  schemas/          Pydantic models (extra="forbid")
  knowledge/
    data/
      standards.yaml    GB 国标条款（30 条）
      rule_cards.yaml   规则卡（32 张）
    fidelity.py     numeric drift 审计 (clause vs rule_card threshold)
    readiness.py    coverage tier 分类
    run_readiness.py  per-run rule_input_readiness.json 生成
  rules/
    engine.py       evaluate(graph, rules, standards, project_meta)
    applicability.py   building_type / height_class gate
  annotate/         标注 PDF + Markdown 报告生成
  feedback/         report.md 复核回写 → rule_cards.yaml test_cases
  adversarial/      examiner ↔ candidate ↔ adjudicator (v1.0.4+)
    examiner.py     L1 deterministic case generator
    adjudicator.py  set-based per-rule TP/FN/FP scoring
    battery.py      run_battery() 调度
  viewer/           static HTTP 渲染过的 out/index.html
  cli/main.py       typer CLI entrypoint

samples/
  sample_clean.pdf       3.6 KB toy demo
  project_meta_demo.yaml
  room_schedule_demo.yaml
  stair_schedule_demo.yaml
tests/                   303 pytest
```

---

## 开发

```bash
# 全套测试
.venv/bin/pytest

# 类型检查（CI 跑这条）
uv run mypy archkg

# Lint
uv run ruff check archkg tests

# 控制面同步（本地快照 + 可选 GitHub/Notion）
archkg control-sync --run-dir tmp/control
archkg control-sync --run-dir tmp/control --github --notion --notion-page-id=<notion-page-id>

说明: `--notion` 会优先尝试页面字段更新；页面不带可写字段时，自动写入该页内子数据库（如有）或回退为可见子块日志。

# 图纸理解 benchmark（识别证据，不是规范判定）
archkg understanding-benchmark out/ --expect samples/understanding_benchmarks/sample_clean_full.json

# 图纸理解 expected spec 草案生成（草案必须人工核对后才能作为 active case）
archkg understanding-benchmark-author out/ --benchmark-id my-plan --out out/expected_understanding.draft.json

# 图纸理解 benchmark suite intake（active 会跑分；known_gap 会记录真实差距）
archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json

# P55: packaged suite 当前 active=7, pending=0, known_gap=0, real_active=3, generated_active=3
# Medfield full-set case 只证明多页识图 evidence 已可追踪，不代表多页合规聚合已完成

# P46: 每次完整 review run 生成 reviewer_onboarding.json / reviewer_quickstart.md
# 用于新手审图工程师第一小时上手，不确认 issue、不改规则结论

# P47: 每次完整 review run 生成 sheet_issue_review_queue.json
# 用于逐页检查 per-sheet preview，不允许直接写入主 review_state.json

# P48: 把已有 run 打成只读交接包
archkg handoff-package out/ -o out-handoff
archkg handoff-check out-handoff
archkg handoff-signoff out-handoff --reviewer reviewer-name --status ready --note "交接包可进入复核"
# repeat for each checklist row that has been reviewed; open rows will hold manager intake at needs_info
archkg handoff-checklist-update out-handoff --ordinal 1 --reviewer reviewer-name --status done --note "已核对边界" --evidence-checked handoff_manifest.json
archkg handoff-ready-runbook out-handoff
archkg handoff-manager-checklist out-handoff --manager manager-name --note "进入复核队列"
archkg handoff-archive-manifest out-handoff --created-by manager-name --note "移交前固化 checksum"
archkg handoff-archive-verify out-handoff
open out-handoff/index.html

# P60: 多交接包负责人索引
archkg handoff-bundle-index handoff-packages/
open handoff-packages/handoff_bundle_index.html

# P62: 新手复核清单会随完整 review run 自动生成
open out/reviewer_task_checklist.md

# P68: 3D layout evidence 会随完整 review run 自动生成
open out/layout_3d_summary.md

# P69: 可选 IFC preview 需要显式导出
archkg ifc export-layout --layout out/layout_3d.json --out out/layout.ifc --report out/layout_ifc_export.json --markdown out/layout_ifc_export.md
# P70: 在有 IfcOpenShell 的环境下，可跑一次真实 smoke 验证
pip install ifcopenshell
archkg ifc export-layout --layout out/layout_3d.json --out out/layout.ifc --report out/layout_ifc_export.json --markdown out/layout_ifc_export.md

# P64: 在交接包内记录单项 checklist 进度
archkg handoff-checklist-update out-handoff --ordinal 1 --reviewer reviewer-name --status done --note "已核对边界" --evidence-checked handoff_manifest.json

# Clause fidelity 审计 (规则卡 vs 国标条款 numeric drift)
archkg clause fidelity

# Coverage tier 分布
archkg clause readiness
```

---

## 研发调研

- [P32 智能审图软件调研与开发指引](docs/research/2026-04-28-intelligent-plan-review-landscape.md) —
  记录 Solibri / IDS / BCF / CORENET X / Archistar eCheck / 国内 BIM 智能审图等参考,
  并把后续路线收敛到 rule-input readiness、sheet 区域候选、issue lifecycle 和 IFC/IDS side lane。
- [P32 后重大转向路线图](docs/strategy/2026-04-28-major-pivot-roadmap.md) —
  将项目主线从“扩大规则/识别数量”转为“证据优先的审图可信度平台”。
- [P68 3D Layout 开源调研与实现路线](docs/research/2026-04-29-3d-layout-model-oss-survey.md) —
  记录 floorplan-to-3D、room polygon reconstruction、CubiCasa、IfcOpenShell 和 trimesh 参考,
  并把第一阶段收敛为 ArchReview-KG 自己的证据化 2.5D layout 模型。
- [新手审图工程师第一小时 Playbook](docs/reviewer/novice-reviewer-playbook.md) —
  面向第一次接触本工具的审图工程师，说明如何从 Viewer / quickstart / readiness / review-state
  完成首轮复核和交接。

---

## 路线

完整 changelog 见 [CHANGELOG.md](CHANGELOG.md)。

当前 repo 内规划真值在 [.planning/](.planning/)：

- [PROJECT.md](.planning/PROJECT.md)：P32 后项目北极星与不可越过的能力边界。
- [ROADMAP.md](.planning/ROADMAP.md)：P33-P43 证据优先路线图。
- [STATE.md](.planning/STATE.md)：当前阶段、风险与下一步。

**P32 后新主线**：

- P33：Rule-input readiness dashboard。每次 run 说明每张规则为什么 ready / missing / low confidence / manual-only / not applicable。
- P34：sheet-region 自动候选建议。先输出候选区域和排除证据，不默认自动裁剪。
- P35：issue lifecycle / review state。规则引擎输出 candidate，人审状态写入 `review_state.json`，再 confirmed / rejected / needs_info / resolved / superseded。
- P36：IFC/IDS side lane。`archkg ifc validate` 复用 IfcOpenShell / IfcTester，不重造完整 BIM checker，输出独立 IFC evidence artifacts。
- P37：rule-card authoring / citation assistant。`archkg rule-card draft` 只产 `rule_card_draft.v1` 草稿，人工确认前不进入 active rule_cards。
- P38：multi-sheet classification。`sheet_classification.json` 先把多页套图中的 plan / schedule / title / legend / detail / elevation / unknown 作为路由证据展示；`sheet_routing.json` 再以保守条件把单一高置信 plan 页送入 graph，否则回退 legacy 全页输入。
- P39：multi-plan graph outputs。`sheet_graphs.json` 为每个高置信 plan sheet 生成独立 graph 证据；`sheet_issues.json` 生成 per-sheet candidate issue preview。主 `entity_graph.json`、`issues.json` 和 `review_state.json` 暂不自动聚合多 plan 页。
- P40：benchmark expansion。Understanding benchmark suite 现在能校验 multi-plan artifacts，并新增 `generated-multi-plan-sheets` active case；真实 Medfield full plan set 先以 `known_gap` 登记，暴露 full-set opening evidence 尚未进入 primary drawing-understanding 的缺口。
- P41/P56/P57/P59：Studio readiness workbench。`review_workbench.json` 与结果页“审图工作台总览”把分散 evidence 汇总成 reviewer 入口，提供 action links 跳到对应面板，提供 `archkg review-state` 本地复核状态操作模板，并支持按页 issue bbox 定位；source/annotated 预览可多页切换，graph-backed entity overlay 也可按页切换，非第一页 primary issue 可切到对应页高亮。主规则结论不变。
- P42：Re-run diff / resolution tracking。`archkg review-diff` 比较两个 run 的主 `issues.json`，写出 `review_diff.json`，不用随机 issue/entity IDs，改用稳定指纹标记 unchanged / changed / new / resolved；Viewer/Studio 只读显示 diff，不回写规则输出或人工复核状态。
- P43：Release readiness gate。`archkg release-readiness` 汇总 benchmark suite 与代表性 run artifacts，输出 `not_ready` / `demo_ready_with_known_gaps` / `evidence_ready`，把 known gaps、pending rows 和 generated-heavy proof 从发布宣称里显式剥离。
- P44：Real drawing benchmark promotion。`drawing_understanding.json` 合并 `sheet_graphs.json` 的多页识图计数，Medfield full-set 从 known_gap 晋升为 active；P44 结束时 release-readiness 只剩 pending row warning。
- P45：Release readiness tightening。`sample_clean_full` toy fixture 从 manual row 固化为 active reproducible fixture；packaged suite 当前 active=5、pending=0、known_gap=0，代表性 run artifacts 完整时可得到 `evidence_ready`，但宣称范围仍限于 benchmarked drawing classes。
- P46：Novice reviewer onboarding。完整审图 run 新增 `reviewer_onboarding.json` / `reviewer_quickstart.md`，报告和 Viewer 显示第一小时流程、常用命令、边界提醒和交接检查，让新手审图工程师按 evidence 顺序上手。
- P61：Reviewer task sequencing。完整审图 run 新增 `reviewer_task_sequence.json` / `.md`，把 readiness blockers、主 `issues.json` open issue、per-sheet preview queue 和 handoff 操作排成有优先级的复核任务；它只排序 evidence，不写 `review_state.json`。
- P62：Reviewer task checklist。完整审图 run 新增 `reviewer_task_checklist.json` / `.md`，从任务序列派生可人工填写的 reviewer_status、note、evidence_checked 清单；它只做交付留痕种子，不确认 issue、不写 `review_state.json`。
- P63：Bundle checklist risk aggregation。`archkg handoff-bundle-index` 读取各包的 `artifacts/reviewer_task_checklist.json`，汇总 checklist open item、blocked/needs_info item 和每包 checklist_review_status；它只做负责人 triage，不改变 `package_status`。
- P64：Package-local checklist update。`archkg handoff-checklist-update` 只更新交接包内 `artifacts/reviewer_task_checklist.json/.md` 并刷新包内 `index.html`，让 reviewer 记录单项完成情况；它不写源 run 或主 `review_state.json`。
- P65：Manager checklist reviewer gate。`archkg handoff-manager-checklist` 会读取包内 reviewer checklist 完成度；未完成清单让 manager intake 保持 needs_info / blocked，不再把 quality+signoff ready 误当成交接清单已闭环。
- P66：Ready-to-review runbook。交接包根目录新增 `handoff_ready_runbook.json/.md`，`archkg handoff-ready-runbook` 可刷新新手下一步动作；open checklist 会生成对应 `handoff-checklist-update` 命令，全部闭环后只剩 manager checklist 或进入 ready。
- P67：Bundle next-actor queue。`archkg handoff-bundle-index` 现在输出 `next_action_queue`，并在每包行里展示 next_actor / next_action / next_action_command；负责人不用打开每个包也能分派下一步。
- P68：Evidence 3D layout model。完整 CLI/Studio run 会基于 `sheet_graphs.json` 优先、`entity_graph.json` 兜底生成 `layout_3d.json` / `.glb` / summary；Viewer 和 handoff package 会展示/复制这些 2.5D 空间导航证据，但它不是 BIM、不是规范结论，也不进入规则引擎。
- P69：Layout IFC export skeleton。`archkg ifc export-layout` 可从 `layout_3d.json` 显式生成 `layout.ifc` preview 和 `layout_ifc_export.v1` 报告；缺 IfcOpenShell 时清晰降级并不生成 IFC。Viewer 和 handoff package 只把它作为可选 preview artifact，不当作审查级 BIM 或合规结论。
- P70：layout_3d 开始接受 explicit opening evidence 的窗口语义。`build_layout_3d` 在 `Door` 明确标为 window 时生成 `window_opening`，并映射为 IFC `IfcWindow`；`window_opening` 和 `door_opening` 都是 preview 语义，不变更规则引擎。完整可选的真实 IfcOpenShell smoke 也已加入回归套件。
- P71：Opening semantic provenance。`door_opening` / `window_opening` 对象会记录 `properties.opening_semantic`，summary 和 Viewer/Studio 会显示 Opening Semantics；这只说明语义来源，不代表墙体开洞几何或合规结论。
- P72：Opening measurement provenance。`door_opening` / `window_opening` 在 graph 有显式尺寸字段时记录 `properties.opening_measurement`，summary 和 Viewer/Studio 会显示 Opening Measurements；显式高度会替代对应默认高度 assumption，缺失字段仍按 assumptions 展示。这只增强 preview provenance，不产生合规结论。
- P47：Sheet preview review bridge。完整审图 run 新增 `sheet_issue_review_queue.json`，报告、Viewer、workbench 和 release gate 均识别它；该队列只指导人工检查 per-sheet preview，不允许把 preview id 直接写入主 `review_state.json`。
- P48/P58：Real-project handoff package。`archkg handoff-package <run-dir> -o <package-dir>` 把 quickstart、report、workbench、readiness、主 issues/review_state、per-sheet preview queue、diff/readiness gate、preview manifest 引用的 source/annotated/entity overlay 页图等复制成只读交接包，生成 `handoff_manifest.json` 与 `handoff_summary.md`，不写回原 run。若 `preview_pages.json` 引用的页图缺失，handoff quality 会阻塞。
- P49：Handoff package quality gate。`archkg handoff-check <package-dir>` 检查交接包 schema、copy-only 策略、必需 artifact、复制文件存在性和边界提醒，输出 `handoff_package_quality.v1`，缺关键证据时返回 `not_ready`。
- P50：Package reviewer signoff notes。`archkg handoff-signoff <package-dir>` 在交接包内写 `reviewer_signoff.json` / `.md`，记录 ready / needs_info / blocked、阻塞项、待补信息和下一步；不修改源 run，也不确认合规。
- P51：Static handoff package review view。`archkg handoff-package` 生成 `index.html`，`handoff-check` 和 `handoff-signoff` 会刷新它；新手 reviewer 可直接打开静态页面查看边界、质量门禁、复核备注和 artifact 链接。
- P52：Manager checklist export。`archkg handoff-manager-checklist <package-dir>` 在交接包内写 `handoff_manager_checklist.json` / `.md`，由 manifest、quality 和 signoff 推导 `manager_ready` / `manager_needs_info` / `manager_blocked`；它是交接管理信号，不是合规结论。
- P53：Archive manifest checksums。`archkg handoff-archive-manifest <package-dir>` 在交接包内写 `handoff_archive_manifest.json` / `.md`，对稳定包文件记录 SHA-256 和 package digest；它用于移交完整性核对，不写回源 run，也不是合规结论。
- P54：Archive verification/import check。`archkg handoff-archive-verify <package-dir>` 重算稳定包文件 checksum 并写 `handoff_archive_verification.json` / `.md`，输出 `archive_verified` 或 `archive_drift`；它用于收到包后的完整性验收，不是合规结论。
- P55：Complex benchmark expansion。Suite 新增 Medfield A-2 Second Floor Plan 真实单页 expected inventory，以及 generated complex mixed-sheet-set；当前 active=7、real_active=3、generated_active=3，继续维持 generated-heavy proof guardrail。
- P56：Sheet-aware issue focus。Viewer/Studio 不再把 issue focus 限定为第一页；后端按 issue `page_index` 和该页尺寸归一化 bbox，前端只对第一页画预览高亮，非第一页明确显示页码并引导打开 PDF 复核。
- P57：Multi-page preview gallery。Viewer/Studio 写出 `preview_pages.json`、多页 source PNG 和多页 annotated PNG，结果页提供图纸页切换；非第一页 issue focus 可直接切到对应页预览并高亮。
- P58：Handoff preview asset completeness。交接包现在复制 `source.pdf`、`preview_pages.json`、legacy preview PNG 和 preview manifest 引用的所有页图，确保新手 reviewer 打开包内静态 viewer 时不缺图；这仍只是证据交接，不是合规证书。
- P59：Per-page entity overlay rendering。Viewer/Studio 现在会为每个 graph-backed sheet 生成 entity overlay 页图，并写入 `preview_pages.json`；多页交接包会自动复制这些 overlay 页图。没有 graph 的页仍不是“已识别完成”。
- P60：Handoff bundle index。`archkg handoff-bundle-index <packages-root>` 扫描多个交接包，生成 `handoff_bundle_index.json` / `.md` / `.html`，按 ready / needs_info / blocked 汇总 quality、signoff、manager checklist、archive verification 和下一步；它只写父目录索引，不改单包或源 run。
- P63：Bundle checklist risk aggregation。bundle index 现在还汇总 reviewer checklist open item 总数和每包 checklist_review_status，让负责人看到复核清单风险；这不改变 package readiness，也不写单包 artifact。
- P64：Package-local checklist update。交接包接收方可用命令记录 checklist item 的 reviewer_status / note / evidence_checked，供包内 index 和 bundle index 读取；该状态不是 candidate issue 确认。
- P65：Manager checklist reviewer gate。manager checklist 汇总 reviewer checklist status、open/blocked/needs_info item counts，并要求清单完成后才输出 `manager_ready`；这只约束交接包 intake，不确认 issue。
- P66：Ready-to-review runbook。包内 runbook 只做导航和命令提示，不纳入 archive checksum，不确认 candidate issue，也不替代人工复核。
- P67：Bundle next-actor queue。跨包队列只读汇总，不写单包或源 run；它是调度提示，不是质量结论。

---

## 引用 / 国标版本

- GB 50096-2011  住宅设计规范
- GB 50352-2019  民用建筑设计统一标准
- GB 50016-2014 (2018 修)  建筑设计防火规范
- GB 50763-2012  无障碍设计规范

国标全文 PDF 在 `standards_raw/`（仅供 fidelity 比对，不分发）。

---

## License

待定 — 项目当前为内部评估阶段。

---

如果你是第一次到这个仓库，建议从 `archkg demo --meta --room-schedule
--stair-schedule` 开始，再读一遍 [READINESS.md](READINESS.md) 弄清楚现在能做
什么 / 不能做什么，再决定要不要在你自己的图纸上跑。
