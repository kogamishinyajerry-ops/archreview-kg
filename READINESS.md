# ArchReview-KG 生产就绪度 (v1.1.0 / Phase 18)

> 直接回答 "现在能不能给用户上传图纸做自动审批"。

## TL;DR

ArchReview-KG **能跑端到端审图**（上传 PDF → 输出标注 PDF + 复核报告 + issue 列表），
但当前实际能力是 **「辅助审图」而非「全自动审批」**：

- 30/30 国标条款都有规则卡（数据完整 ✅）
- 但 32 张规则中**只有 4 张能在任何 PDF 上直接自动判定违规**（≈ 12.5%）
- 其余规则需要 ProjectMeta 完整、graph builder 扩展、或本就是人工核对清单
- P43 后，成熟度主指标改为 `archkg release-readiness`：用 benchmark suite、代表性 run artifacts、
  review state 和 re-run diff 证据判断能否演示；P45 后当前 packaged suite 可在代表性 run
  artifacts 完整时进入 `evidence_ready`。这个状态仍只适用于已 benchmark 的图纸类别，不是任意复杂
  真实图纸自动审批证明。
- P46 后每次完整 review run 会生成 `reviewer_onboarding.json` / `reviewer_quickstart.md`，
  把新手审图工程师的第一小时复核路径固化为 artifact。
- P47 后每次完整 review run 会生成 `sheet_issue_review_queue.json`，把 per-sheet preview
  收束成有界人工审阅队列，但 preview id 仍不能进入主 `review_state.json`。
- P48 后可用 `archkg handoff-package <run-dir> -o <package-dir>` 生成只读交接包，
  将 quickstart、readiness、diff、preview queue 和边界提醒固化为可移交证据。
- P49 后可用 `archkg handoff-check <package-dir>` 对交接包做独立质量门禁，
  检查 schema、copy-only 策略、必需 artifact、复制件存在性和边界提醒。
- P50 后可用 `archkg handoff-signoff <package-dir>` 在交接包内记录 reviewer 的 ready /
  needs_info / blocked 状态、阻塞项和下一步；它只写包内 note，不是合规证书。
- P51 后交接包根目录会有 `index.html` 静态入口，汇总 boundary、quality、signoff 和 artifact 链接，
  方便新手审图工程师直接打开复核。
- P52 后可用 `archkg handoff-manager-checklist <package-dir>` 生成负责人交接清单，
  把 package quality、reviewer signoff 和必需 artifact 汇总为 manager-level intake 状态。
- P53 后可用 `archkg handoff-archive-manifest <package-dir>` 生成移交完整性清单，
  对交接包内稳定文件记录 SHA-256 和 package digest；它只证明包文件未漂移，不证明图纸合规。
- P54 后可用 `archkg handoff-archive-verify <package-dir>` 在收到包后重算 checksum，
  输出 `archive_verified` 或 `archive_drift`；drift 是交接阻塞，不是图纸违规结论。
- P56/P57 后 Viewer/Studio 的 issue focus 已按图纸页定位，并能基于 `preview_pages.json`
  切换 source / annotated 多页预览：非第一页 issue 可直接切到对应页高亮，避免第一页假定位。
- P58 后 `archkg handoff-package` 会把多页 preview manifest 及其引用页图复制进交接包；
  缺少 manifest 引用的页图会成为 handoff quality blocker。
- P59 后 Viewer/Studio 会为 graph-backed sheet 生成多页 entity overlay 预览，并把这些页图纳入
  `preview_pages.json` 和 handoff 复制链路；没有 graph 的页仍需 source/annotated/PDF 人工核对。
- P60 后负责人可对多个交接包运行 `archkg handoff-bundle-index <packages-root>`，生成批量
  `handoff_bundle_index` JSON/Markdown/HTML，用于筛出 ready / needs_info / blocked 包。
- P61 后完整 run 会生成 `reviewer_task_sequence.json` / `.md`，按 readiness blockers、
  主 issue、per-sheet preview、handoff 动作排序新手 reviewer 的下一步。
- P62 后完整 run 会从任务序列派生 `reviewer_task_checklist.json` / `.md`，供新手
  reviewer 逐项勾选证据、记录 reviewer_status 与未解决风险；该清单不写回
  `issues.json` 或 `review_state.json`。
- P63 后 `handoff-bundle-index` 会读取每个包内的 `artifacts/reviewer_task_checklist.json`，
  汇总 checklist open item 总数、每包 checklist_review_status 和 open samples；它只做负责人
  triage，不改变 package readiness。
- P64 后 reviewer 可用 `archkg handoff-checklist-update <package-dir>` 在交接包内更新单个
  checklist item 的 reviewer_status、note 和 evidence_checked；该命令只写 package-local
  checklist 和 package `index.html`。
- P65 后 `archkg handoff-manager-checklist <package-dir>` 会读取 package-local reviewer
  checklist 完成度；open / needs_info item 会让 manager intake 保持 `manager_needs_info`，
  blocked 或缺失 checklist 会阻塞 manager intake。
- P66 后交接包会写 `handoff_ready_runbook.json` / `.md`；`archkg handoff-ready-runbook`
  可刷新新手 reviewer 的下一步命令清单，直到 checklist 和 manager intake 闭环。
- P67 后 `archkg handoff-bundle-index <packages-root>` 会输出 `next_action_queue`，
  并为每个包标出 next_actor / next_action_command，支持跨包分派 reviewer、manager、archive 下一步。
- P68 后完整 CLI/Studio run 会写 `layout_3d.json`、`layout_3d_summary.md` 和
  `layout_3d.glb`，把已识别的平面 graph 转成证据化 2.5D 空间导航模型；默认层高、墙厚、
  板厚、门洞高度只用于可视化，并在 assumptions 中显式标出，不是 BIM 真值或合规判断输入。
- P69 后可显式运行 `archkg ifc export-layout`，从 `layout_3d.json` 派生可打开的
  `layout.ifc` preview 和 `layout_ifc_export.v1` 报告；它需要可选 IfcOpenShell，
  缺依赖时清晰降级，不生成 IFC，也不影响普通审图流水线。
- P70 后 `layout_3d` 会把明确窗口洞口（`Door` 上有 `opening_kind: "window"` /
  `opening_kind: "window_opening"` 或 `is_window: true`）建模为 `window_opening`，
  并在 IFC preview 导出时映射为 `IfcWindow`。这仍是 preview / evidence 信号，不是
  规则引擎或合规输入。
- P71 后 `layout_3d` 的 `door_opening` / `window_opening` 会携带
  `properties.opening_semantic`，说明语义来自显式 graph evidence 还是默认 Door entity；
  Viewer/Studio 和 summary 会显示 Opening Semantics 摘要，方便 reviewer 审计来源。
- P72 后 `layout_3d` 的 `door_opening` / `window_opening` 在 graph 明确提供
  `Door.width_m`、`Door.properties.height_m`、`sill_height_m` 或 `head_height_m` 时会携带
  `properties.opening_measurement`；Viewer/Studio 和 summary 会显示 Opening Measurements。
  缺失尺寸仍按显式 assumptions 处理，所有 opening measurements 仍只是 preview provenance。
- P73 后 `layout_3d` 只有在 graph 明确提供 opening host wall/source-segment 字段时才写入
  `properties.opening_host`；Viewer/Studio 和 summary 会显示 Opening Host Wall Provenance。
  没有显式 host evidence 时不推断 host，不生成墙体布尔开洞。
- P74 后 Viewer/Studio 和 summary 会显示 Opening Provenance Consistency，把 semantic、
  measurement、host 三类 opening 证据面合并成 coverage 视图。缺失项是复核提示，不是失败、
  合规结论或 BIM 完整性声明。
- P75 后 `layout_ifc_export.v1` 和 IFC Viewer 数据会透传 opening provenance coverage KPI；
  它只是 optional IFC preview 的元数据，不把 `layout.ifc` 升级为审查级 BIM。
- P76 后交接包的 manifest、summary 和静态 `index.html` 会显示 opening provenance coverage，
  让新手 reviewer 在包入口看到 semantic / measurement / host_wall / all_three 覆盖；
  缺失项仍只是复核提示，不是 handoff quality blocker 或合规结论。
- P77 后 `handoff-bundle-index` 会跨包汇总 opening provenance coverage，并标出 weak
  coverage 包数量，供负责人分派复核。
- P78 后 bundle index 还会输出独立 `opening_provenance_triage_queue`，把 weak coverage
  包列为 reviewer triage 项；它与正常 `next_action_queue` 分离，不改变 readiness 或交接状态。
- P79 后 weak opening provenance 会进入包内 reviewer checklist guidance 区，提示缺失的
  semantic / measurement / host_wall 信号；它不新增 checklist item，不改变 manager readiness。

复现该结论：

```bash
archkg clause readiness
archkg release-readiness \
  --manifest samples/understanding_benchmarks/suite_manifest.json \
  --run-dir out/ \
  --out out/release_readiness.json \
  --markdown out/release_readiness.md
```

## P43 发布/演示门禁

`archkg release-readiness` 输出三个状态：

| status | 含义 |
|---|---|
| `not_ready` | active suite 失败、没有 active 真实图纸、或代表性 run 缺核心 artifacts。不能对外用作成熟度信号。 |
| `demo_ready_with_known_gaps` | 可演示证据优先审图工作台，但必须同时展示 known gaps、pending fixtures 和人工复核边界。 |
| `evidence_ready` | active suite 通过、没有 known_gap / pending rows、代表性 run 具备核心和成熟度 artifacts。仍只适用于已 benchmark 的图纸类别。 |

当前 packaged suite 的门禁烟测结果：

```text
release-readiness status=evidence_ready blockers=0 warnings=0 active=7 real_active=3 known_gap=0
```

这意味着：项目可以演示“识图证据、规则输入就绪度、候选问题、人工复核状态、重跑 diff、新手上手包、per-sheet 预览审阅队列、按页 issue focus、2.5D 空间导航模型、只读交接包、包内复核备注、静态交接入口、负责人交接清单”
组成的闭环；P44 已把 Medfield 9 页真实 full-set 从 known_gap 晋升为 active recognition benchmark。
P55 又补入 Medfield A-2 第二张真实单页 expected inventory 和一个 generated mixed-sheet-set 复杂回归样本，
使 active=7、real_active=3、generated_active=3，仍避免 generated-heavy proof 超过真实图纸证据。
但 `layout_3d` / `layout.ifc` 仍是从当前 graph 推导的辅助导航层，Opening Semantics、
Opening Measurements、Opening Host Wall Provenance 和 Opening Provenance Consistency
只解释来源与覆盖；P75-P79 把同一组 coverage 透传到 IFC export summary、handoff package、
bundle summary、独立 triage queue 和包内 reviewer checklist guidance，
但仍不代表墙洞几何已准确建模；per-sheet preview issues 还没有进入主 lifecycle，
且真实复杂图纸覆盖仍有限，所以仍不能宣称
“已能处理任意复杂真实设计图并自动精准纠错”。

## 32 张规则的就绪度分布

| tier | 数量 | 含义 | 真实例子 |
|---|---|---|---|
| **AUTODETECTABLE** | 4 | 上传图纸即可自动判违规 | 户门净宽 < 0.90 m / 走廊净宽 < 1.20 m / 卧室面积 < 5.0 m² |
| **PROJECT_META_DRIVEN** | 1 | 用户填 ProjectMeta（住房套数、无障碍套数）即可自动判 | 无障碍住房比例 < 2/100 |
| **PARTIAL_AUTODETECT** | 4 | 规则正确但需 entity properties — v1.0.2 新增 `--room-schedule` 手动数据路径 | 卧室净高 < 2.40 m（净高来自剖面图，builder 不抽，但 schedule.yaml 可填） |
| **STAIR_PENDING** | 5 | 规则+引擎已就位，等 graph builder 加 PDF 楼梯检测 | 楼梯踏步 < 0.26 m / 踢面 > 0.175 m / 扶手 < 0.90 m |
| **REMINDER_BY_DESIGN** | 18 | severity=info，提供"人工核对清单"而非自动结论 | "项目为住宅，请核对外窗窗台 < 0.90 m 时是否设防护设施" |

**总计**: 4 + 1 + 4 + 5 + 18 = 32 张规则。

- **从图纸单独自动判定上限** = 4 张（默认 builder 能力）
- **+ ProjectMeta** = 5 张（户均套数等项目级数据）
- **+ Room Schedule** = 9 张（v1.0.2 新增；用户填 `--room-schedule schedule.yaml` 提供净高 / 楼层 / 坡屋顶，解锁 4 张 PARTIAL_AUTODETECT）
- 剩余 5 张楼梯规则等 Phase 19+ 楼梯检测；18 张 reminder 是设计上的人工清单

## 当前 demo 实际跑出来什么

```bash
archkg demo --meta
```

跑 `samples/sample_clean.pdf`（toy demo）+ ProjectMeta（`samples/project_meta_demo.yaml`：演示住宅 6F/18m，建筑类别二级、寒冷气候）。

stdout 打印一组 Rich 表格：项目上下文 / 实体识别 / 跳过的规则 / 问题清单 23 行 flat 表。
分区视图（违规 vs 提醒）在生成的 `out/report.md`：

```
实体识别: rooms=4 doors=6 corridors=1 dimensions=3
因项目上下文跳过的规则: 1 (RC-REFUGE-LAYER-100M, 仅适用超高层)
问题清单 (共 23 条):
  - 6 个 error 级（out/report.md § 违规清单）：
    · RC-DOOR-WIDTH × 4（户门 0.85 m < 0.90 m）
    · RC-CORRIDOR-WIDTH × 1（走廊 1.05 m < 1.20 m）
    · RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20 × 1（同一走廊，无障碍标准）
  - 17 个 info 级（out/report.md § 人工核对提醒）
```

叠加 `--room-schedule`：

```bash
archkg demo --meta --room-schedule
```

加载 `samples/room_schedule_demo.yaml`（adversarial: bedroom in basement / pitched-roof living / basement bathroom / kitchen 对照组）。问题清单从 23 → **27**，新增 4 个 error 级触发自 4 张 PARTIAL_AUTODETECT 规则:

```
RC-LIVING-BEDROOM-NETHEIGHT-2.4    bedroom 净高 2.30 < 2.40
RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1   living 坡屋顶 majority 2.00 < 2.10
RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0      bathroom 地下室 1.80 < 2.0
RC-NO-LIVING-IN-BASEMENT                 bedroom 位于 basement
```

`out/report.md` 自动分两区：
- **违规清单** severity=error：baseline 6 项；叠加 `--room-schedule` 后变 10 项（多出 4 张 PARTIAL_AUTODETECT 规则触发）
- **人工核对提醒** severity=info：17 项

## v1.2 新增 — Studio 上传界面 + 真实 PDF 案例研究

### Studio (v1.2.0)

```bash
archkg studio
```

启动 Flask 上传界面 (默认 8765)。第一次接触工具的用户拖 PDF 即可完整跑通流程，
也可点 "跑内置 demo" 用 `samples/sample_clean.pdf` 看完整效果。

### 真实 PDF 案例 — Medfield 公寓 (v1.2.1)

实地测试: 美国 [Medfield 16-unit apartment plans](https://www.town.medfield.net/DocumentCenter/View/1428/floorplans-and-elevations-04-10-18-PDF)
(政府公开 CAD 导出 PDF, 9 页, 单页 8.5k 矢量路径)。

**结果**: 4.2 秒处理完, 不崩溃, 但输出**主要是噪声**:
- 检出 169 房间 (实际 ~80) — over-segmentation
- 检出 204 户门 (大多是窗框/家具/橱柜的间隙)
- 89 个 RC-DOOR-WIDTH 违规 — 大多假阳性 (门宽 0.80-0.83m 集中分布是 builder 把 fixture 间隙当成 door)

**v1.2.1 应对**: studio 上传表单加了
- **points_per_meter** 字段: PDF 比例尺 (默认 50 适配 metric CAD 导出, US 制图需调整)
- **仅识图模式** 复选框: 只跑 ingest + build_graph + entity overlay, 跳过规则评估。
  适合不熟悉的 PDF 先看 builder 检出实体数量是否合理, 再决定要不要让规则跑
- **质量标记**: rooms > 50 / doors > 50 / 无 corridor 时, 结果页顶部红色横幅提示
  "builder 可能 over-segmenting, 规则违规需谨慎解读"

**v1.2.2 应对** (builder-side noise filter):
- **`min_room_area_m2`** 表单字段 (默认 1.0 m²): 在 builder 内部丢弃低于阈值的多边形,
  让 window frames / 标注框 / fixture 轮廓在变成 "rooms" 之前被过滤
- 同样的 floor 也作用于 corridor 分类分支, 长条窄缝 (橱柜间隙等) 不会假装成 corridor
- 配套**邻接式门过滤**: 与被过滤多边形相邻的 wall break 不再变成 Door, 避免 noise
  rule fire (RC-DOOR-WIDTH 等)
- **已知限制**: 邻接判定假设墙是零厚度线段。Synthetic 样例 + 部分 metric CAD 导出符合,
  但**没有在足够多真实图纸上验证**。**双线墙 CAD** (内/外两条平行线 + 中间墙体) 的 door bridge
  落在墙体 centerline 内, 可能让所有 door 邻接判定都失败 → 全被丢弃。
  **症状**: 结果里 door 数量为 0 或明显偏少。**应对**: CAD 里把双线墙合并为单线再导出, 或等 v1.3+ 处理

**v1.4-dev 应对** (raster OCR + drawing understanding bridge):
- PNG/JPEG/TIFF/BMP 上传可选启用 **栅格 OCR beta**。OCR 成功时，文本作为
  `TextPrimitive(source="ocr")` 写入 `primitives.json`，并参与 room label binding。
- 结果页新增 OCR 证据面：展示 OCR text count、绑定房间数、低置信度数量与样例文本行；
  standalone `archkg viewer` 从 run artifacts 重渲染时也保留该证据面。
- OCR 证据面新增 label QA candidates：label 冲突、未绑定高置信度 label、低置信度 label
  只作为人工复核提示，不自动修改 `Room.label`，也不改变规则结论。
- OCR 数字文本新增 Door/Corridor 尺寸绑定证据：展示 OCR 值、绑定实体与实体当前尺寸值；
  这是对既有 dimension binding 路径的审计展示，不新增合规输出通道。
- OCR 不作为默认依赖；本机未安装 PaddleOCR 或 OCR 返回空时，流水线不崩溃，
  继续按 partial 审图降级，并保留 "栅格图无 OCR" 质量提示。
- 这不是 production OCR 准确率承诺。OCR-bound room labels 仍需人工核对，
  噪声扫描图 / 手绘图纸仍可能无法可靠识别。
- 结果页新增 `drawing_understanding.json` + "图纸理解摘要" 面板：汇总图纸类型、
  可能设计对象、空间 / 门洞 / 通行部件清单，以及 graph/OCR 尺寸证据绑定状态。
  这是识图闭环和人工复核入口，不是新的规范纠错通道，也不代表复杂真实施工图已经可全自动理解。
- P24 起 `drawing_understanding.json` 升级为 v2 schema：增加 typed `component_inventory`、
  `drawing_profile` 与 `benchmark_signals`。楼梯/垂直交通从 stair schedule 或未来 builder 输出进入
  同一部件清单；旧 run 目录里的 P23 摘要会在 standalone viewer 重渲染时自动重建为 v2。
  这些字段服务于"识别到什么"的横向基准，不提升 OCR/CV 准确率，也不扩大规范纠错范围。
- P25 新增 `archkg understanding-benchmark <run-dir> --expect <spec.json>`：把 run 目录里的
  `drawing_understanding.json`（或从 `primitives.json + entity_graph.json` 自动构建的 v2 摘要）
  与期望部件清单、证据信号、benchmark flags 比对，输出 JSON / Markdown 跑分。
  当前只随仓库提供 `samples/understanding_benchmarks/sample_clean_full.json` 作为 toy fixture 基准；
  真实复杂图纸需要逐个加入期望清单后才能形成有效 benchmark。
- P26 新增 `archkg understanding-benchmark-suite --manifest <suite.json>`：把多个识图 benchmark case
  放进同一个 suite manifest。`active` case 会检查 run artifacts 并跑分；`pending_fixture` /
  `manual_run_required` 只登记真实图纸或待生成样例，不计为通过证明。仓库里的
  `samples/understanding_benchmarks/suite_manifest.json` 是 intake 模板，用于后续接入真实公开图纸
  和人工标注的 expected inventory。
- P27 新增 `archkg understanding-benchmark-author <run-dir> --out <draft.json>`：从当前 run 的
  `drawing_understanding.json` 生成 expected inventory 草案，包含图纸类型、部件计数、semantic kinds、
  evidence signals 与 positive benchmark flags。草案带 `review_required: true`，必须人工核对和调整后
  才能把真实图纸 case 从 `pending_fixture` 提升为 `active`。
- P28 开始接入真实图纸 expected inventory：`suite_manifest.json` 现在包含 Medfield / Hillside Village
  A-1 First Floor Plan 的人工 expected inventory、来源 provenance 和当前 `drawing_understanding.json`
  快照。该 case 标为 `known_gap`：suite 会真实跑分并记录 rooms/doors 过分割与 stair/vertical
  circulation 缺失，但不把这张真实图纸包装成已通过能力。
- P44 已把 Medfield 9 页 full plan/elevation set 从 known_gap 晋升为 active recognition benchmark：
  opening evidence 来自 `sheet_graphs.json` 的多页计数汇总，不代表 per-sheet issue 已自动进入主审图结论。
- P45 已把 `sample_clean_full` toy row 从 `manual_run_required` 固化为 deterministic active fixture：
  它只清理可复现门禁，不扩大真实图纸能力宣称。
- P55 新增 Medfield A-2 Second Floor Plan 真实单页 expected inventory，并新增 generated mixed-sheet-set
  复杂回归样本；packaged suite 当前 active=7、pending=0、known_gap=0，real_active=3、generated_active=3。
  这扩大的是 benchmark 覆盖，不是任意复杂真实图纸自动审批证明。
- P46 新增 `reviewer_onboarding.json` / `reviewer_quickstart.md`：完整 review run 会生成新手第一小时流程、
  常用命令、不要误宣称的边界和交接清单；该 artifact 是 guidance-only，不确认 issue、不修改规则结论。
- P47 新增 `sheet_issue_review_queue.json`：完整 review run 会把 `sheet_issues.json` preview rows
  收束为 `preview-only bounded bridge`，供人工逐页核对；它不创建主 issue id，也不允许
  `archkg review-state` 写入这些 preview rows。
- P48 新增 `archkg handoff-package`：从已有 run 复制交接所需 artifacts 到独立目录，
  写出 `handoff_manifest.json` 与 `handoff_summary.md`；该操作不修改源 run，不确认 issue。
- P49 新增 `archkg handoff-check`：读取交接包并输出 `handoff_package_quality.v1`；
  缺少必需 artifact、复制件丢失或边界提醒缺失时返回 `not_ready`。
- P50 新增 `archkg handoff-signoff`：在交接包内写 `reviewer_signoff.json` / `.md`，
  记录 reviewer、ready / needs_info / blocked 状态、阻塞项、待补信息和下一步；该命令不修改源 run，
  不确认 candidate issue。
- P51 新增交接包静态 `index.html`：`handoff-package` 创建入口，`handoff-check` 和 `handoff-signoff`
  刷新 quality/signoff 摘要；该页面只是浏览入口，不产生新 evidence。
- P52 新增 `archkg handoff-manager-checklist`：读取包内 manifest、handoff quality 和 reviewer signoff，
  写出 `handoff_manager_checklist.v1` JSON/Markdown，并刷新静态入口；该清单只判断交接包是否可进入下一步复核。
- P53 新增 `archkg handoff-archive-manifest`：读取交接包并写出 `handoff_archive_manifest.v1` JSON/Markdown，
  对 `artifacts/*` 和包根 metadata 记录 SHA-256、size 和 package digest；该命令不修改源 run，不是合规证书。
- P54 新增 `archkg handoff-archive-verify`：重算交接包稳定文件 checksum，
  写出 `handoff_archive_verification.v1` JSON/Markdown，并在缺失、变更或多出文件时返回 `archive_drift`。

### 对抗训练 lane (v1.0.4-v1.0.9)

Phase 18-D 起加了 examiner ↔ candidate ↔ adjudicator 对抗 lane (`archkg adversarial`)。
21 张规则被 deterministically 触发, 100-case battery 全 pass at F1=1.00:

```bash
archkg adversarial run -n 100 --seed 5000        # 跑对抗 battery
archkg adversarial sample-stats -n 1000 --seed 5000   # 审计 per-rule 触发率
```

这 lane 在 v1.0.4-v1.0.9 6 ships 里:
- v1.0.5: 暴露并修了 builder polygonize snap bug (recall 0.88 → 1.00)
- v1.0.6: 暴露并修了 examiner 自身 height_class 分类 bug (5 个 spurious FN → 0)
- v1.0.7-9: 加 8 张新规则到 targeted set + sample-stratification 自我审计

意义: 不再只是 metric tooling, 而是 systematic blind-spot finder。
每加新规则 / 每改 rule_cards 都自动暴露 mismatch.

## "100% coverage" 真正含义

- ✅ 30 条国标都已建模为规则卡
- ✅ 规则 logic 都过 fidelity 闸 + Codex 审
- ✅ 引擎、feedback、verbatim audit、CLI、报告模板都已对齐
- ❌ 不等于 "上传任何图纸即自动产生通过/驳回结论"

把 v1.0 当作**规则知识库与引擎的完整态**，而非**生产可用审图服务**。

## P32 后重大转向：先做可信度平台，再扩自动审查

P32 调研后，项目主线从“继续扩规则数量 / 继续扩视觉识别数量”调整为
**证据优先的智能审图可信度平台**。

成熟审图软件与政府级 BIM 审查实践的共同模式是：先定义输入交付要求和证据来源，
再运行规则，再把发现变成可复核的 issue 生命周期。ArchReview-KG 也应采用这个路径。

新的近期路线：

1. **P33 Rule-input readiness dashboard**
   - 每次 run 为 32 张规则输出 `ready / missing_input / low_confidence / manual_only / not_applicable`。
   - 目标是让用户明确知道“哪些规则真的可判、哪些规则缺证据”，而不是只看 issue 数量。

2. **P34 Sheet-region candidate suggestions**
   - 在 P31 手动 `--sheet-region` 基础上，自动建议 design / title block / schedule / legend 区域。
   - 默认只提示，不自动裁剪，避免静默丢失设计证据。

3. **P35 Issue lifecycle / review state**
   - 规则引擎只输出 candidate。
   - 人工复核再进入 `confirmed / rejected / needs_info / resolved / superseded`。
   - 为后续 BCF-like export 做准备。

4. **P36 IFC/IDS side lane**
   - 复用 IfcOpenShell / IfcTester 做 IFC + IDS 校验 spike。
   - PDF 图纸识别和 IFC 模型检查保持解耦，不重造完整 BIM checker。

5. **P37 Rule-card authoring / code-citation assistant**
   - AI 只生成 draft rule-card / citation / ambiguity notes。
   - 人工确认前不得进入 active `rule_cards.yaml`，也不得生成最终违规。

新的 readiness 评价标准：

- 不再以 rule count 作为成熟度主指标。
- 以真实图纸 expected inventory、每次 run 的规则输入就绪度、证据来源绑定、issue 复核状态、
  rerun 后问题是否 resolved 为主要指标。
- P43 起，发布/演示宣称必须经过 `archkg release-readiness`，并把输出状态和 warnings
  一起展示；`generated_*` fixture 只能做回归锁定，不能替代真实图纸成熟度证明。生成样本数量多于
  active 真实图纸证据时，门禁会继续阻止 `evidence_ready`。
- P44 起，`drawing_understanding.json` 可把 `sheet_graphs.json` 的多页 plan graph 计数合并为
  full-set recognition evidence；该 evidence 不会自动合并 per-sheet issues 到主 `issues.json`。
- P45 起，packaged release gate 可在代表性 run artifacts 完整时输出 `evidence_ready`；该状态应解释为
  “benchmarked drawing classes 的受限试点证据就绪”，而不是 production certification。
- P46 起，readiness gate 也把 reviewer onboarding artifacts 视为 maturity evidence；交付前不仅要看模型输出，
  还要看新手能否按 `reviewer_quickstart.md` 完成复核与交接。
- P47 起，readiness gate 也要求 `sheet_issue_review_queue.json`；它证明 per-sheet preview 有可执行的人工审阅入口，
  但不代表多页候选问题已经自动聚合为主违规结论。
- P48 起，交付前建议另跑 `archkg handoff-package` 生成只读包；它是交接完整性证据，
  不是 release-readiness gate 的替代品。
- P49 起，交付前还应跑 `archkg handoff-check`；它只验证交接包完整性，
  不替代图纸识别 benchmark 或 release-readiness。
- P50 起，交接复核可以用 `archkg handoff-signoff` 收口为包内 note；ready 只表示交接包可进入下一位 reviewer
  流程，不表示图纸合规。
- P51 起，交接包可直接打开 `index.html` 给新手 reviewer 使用；页面上的状态来自既有 artifacts，
  不替代源 run、benchmark 或人工复核。
- P52 起，负责人可用 manager checklist 做 intake；`manager_ready` 不是图纸合规，只表示交接包本身满足进入下一轮复核的条件。
- P53 起，移交前可用 archive manifest 做 checksum 固化；`archive_manifest_ready` 只表示包内文件有完整性清单，
  不替代 source run、benchmark、release-readiness 或人工复核。
- P54 起，收到包后可用 archive verification 做 drift 检查；`archive_verified` 只表示 checksum 对齐，
  不表示任何 candidate issue 已确认或图纸合规。
- P55 起，release-readiness 仍要求真实图纸证据不少于生成样本证据；新增 generated mixed-sheet-set
  没有放宽该 guardrail，而是同时补入第二张 Medfield 真实单页 expected inventory。
- P57/P59 起，source / annotated / graph-backed entity overlay 静态 PNG 预览已经支持多页切换；
  preview pages 只是导航/复核辅助，不能当成合规结论或完整识图证明。
- P58 起，交接包会保全多页 preview assets；这只提升包内静态 viewer 可用性，
  不表示 candidate issue 已确认或图纸合规。
- P60 起，bundle index 只汇总多个 package 的交接状态，不写入单包或源 run；
  `bundle_ready` 不是图纸合规，也不是 release-readiness 的替代品。
- P61 起，reviewer task sequence 只是复核顺序，不会自动确认 issue、不会写
  `review_state.json`，也不会把 preview issue 提升为主 issue。
- P62 起，reviewer task checklist 只是人工填写的清单种子，不会自动完成任务、
  确认 issue、写入 `review_state.json`，也不是合规证书。
- P63 起，bundle checklist risk 只是跨包只读汇总；它不修改单包 artifacts，也不把
  checklist 状态当成图纸合规状态。
- P64 起，handoff checklist update 只记录交接包内的复核进度；它不写源 run、
  不写主 `review_state.json`，也不确认 candidate issue。
- P65 起，manager checklist 要求 reviewer checklist 完成后才输出 `manager_ready`；
  该 gate 只说明交接包可进入负责人下一步 intake，不说明图纸合规。
- P66 起，ready-to-review runbook 是包内导航面和命令提示；它不纳入 archive checksum，
  不确认 candidate issue，也不替代人工复核或经理 intake。
- P67 起，bundle next-actor queue 是只读调度提示；它不修改单包、不替代包内 runbook，
  也不改变 package readiness 或合规状态。
- P76 起，handoff opening provenance coverage 是包内导航提示；它不改变 handoff quality、
  reviewer checklist、manager checklist、archive verification 或图纸合规状态。
- P77/P78 起，bundle opening provenance aggregation 和 triage queue 只帮助负责人跨包分派 reviewer；
  它不改变 package readiness、normal next action queue、handoff quality 或图纸合规状态。
- P79 起，package-local opening provenance checklist guidance 不新增 checklist item，不改变
  checklist completion、manager readiness、source run 或图纸合规状态。

repo 内规划真值见 `.planning/PROJECT.md`、`.planning/ROADMAP.md`、`.planning/STATE.md`。

## 给现在想用的人的指引

如果想**今天就用**：
- 用例：审住宅平面图，重点看户门尺寸 / 走廊宽度 / 卧室面积 / 净高 / 地下室用途
- 步骤：填 ProjectMeta + Room Schedule YAML → `archkg review --project-meta meta.yaml --room-schedule schedule.yaml plan.pdf`
- 期望：6 + 4（如果 schedule 命中违规）个左右 error 级违规自动发现 + 17 项人工核对清单
- 不要期望：楼梯类（Phase 19+）、户门 subtype、PDF 自动抽净高/楼层（Phase 20+）

如果想**等 production-ready**：
- 关注 `archkg release-readiness` 的 `evidence_ready` 状态，而不是只看 AUTODETECTABLE 数量。
- 等 known_gap / pending 真实图纸 case 被人工 expected inventory 推进为 active 且持续通过后，再扩大试点图纸类别。

## 状态查询

```bash
archkg clause readiness     # 各 tier 分布 + 逐条详情
archkg clause coverage      # 30/30 标准条款覆盖
archkg clause fidelity      # 数值保真闸 0 errors
archkg clause verbatim      # paraphrase clause 与 PDF 原文对照
archkg demo --meta          # 端到端 demo（包括样例 ProjectMeta）
archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir out/
```
