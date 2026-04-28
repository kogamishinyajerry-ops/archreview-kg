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
release-readiness status=evidence_ready blockers=0 warnings=0 active=5 real_active=2 known_gap=0
```

这意味着：项目可以演示“识图证据、规则输入就绪度、候选问题、人工复核状态、重跑 diff、新手上手包、per-sheet 预览审阅队列”
组成的闭环；P44 已把 Medfield 9 页真实 full-set 从 known_gap 晋升为 active recognition benchmark。
P45 清理了最后一个 packaged `manual_run_required` toy row，使 release gate 的技术前提完整。
但 per-sheet preview issues 还没有进入主 lifecycle，且真实复杂图纸覆盖仍有限，所以仍不能宣称
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
  packaged suite 当前 active=5、pending=0、known_gap=0。它只清理可复现门禁，不扩大真实图纸能力宣称。
- P46 新增 `reviewer_onboarding.json` / `reviewer_quickstart.md`：完整 review run 会生成新手第一小时流程、
  常用命令、不要误宣称的边界和交接清单；该 artifact 是 guidance-only，不确认 issue、不修改规则结论。
- P47 新增 `sheet_issue_review_queue.json`：完整 review run 会把 `sheet_issues.json` preview rows
  收束为 `preview-only bounded bridge`，供人工逐页核对；它不创建主 issue id，也不允许
  `archkg review-state` 写入这些 preview rows。

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
