# ArchReview-KG 生产就绪度 (v1.1.0 / Phase 18)

> 直接回答 "现在能不能给用户上传图纸做自动审批"。

## TL;DR

ArchReview-KG **能跑端到端审图**（上传 PDF → 输出标注 PDF + 复核报告 + issue 列表），
但当前实际能力是 **「辅助审图」而非「全自动审批」**：

- 30/30 国标条款都有规则卡（数据完整 ✅）
- 但 32 张规则中**只有 4 张能在任何 PDF 上直接自动判定违规**（≈ 12.5%）
- 其余规则需要 ProjectMeta 完整、graph builder 扩展、或本就是人工核对清单

复现该结论：

```bash
archkg clause readiness
```

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

**v1.4-dev 应对** (raster OCR bridge):
- PNG/JPEG/TIFF/BMP 上传可选启用 **栅格 OCR beta**。OCR 成功时，文本作为
  `TextPrimitive(source="ocr")` 写入 `primitives.json`，并参与 room label binding。
- 结果页新增 OCR 证据面：展示 OCR text count、绑定房间数、低置信度数量与样例文本行；
  standalone `archkg viewer` 从 run artifacts 重渲染时也保留该证据面。
- OCR 证据面新增 label QA candidates：label 冲突、未绑定高置信度 label、低置信度 label
  只作为人工复核提示，不自动修改 `Room.label`，也不改变规则结论。
- OCR 不作为默认依赖；本机未安装 PaddleOCR 或 OCR 返回空时，流水线不崩溃，
  继续按 partial 审图降级，并保留 "栅格图无 OCR" 质量提示。
- 这不是 production OCR 准确率承诺。OCR-bound room labels 仍需人工核对，
  噪声扫描图 / 手绘图纸仍可能无法可靠识别。

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

## 走到"真自动审批"还需要什么

按 ROI 排序：

### 高 ROI（解锁现有规则）

1. **graph builder 加 Room.properties 自动抽取** ← v1.0.2 已开手动数据路径 `--room-schedule`
   - 当前：`samples/room_schedule_demo.yaml` 等 YAML 让用户填净高 / 楼层 / 坡屋顶 → 4 张 PARTIAL_AUTODETECT 规则可触发
   - 下一步：从剖面图 / 图签 / 楼层结构自动产出同一份数据，让 schedule 退化为 override
   - 难点：净高来自剖面图（不在平面图）；level / pitched_roof 来自图签或楼层标识
   - 依赖：CAD/PDF 多页面理解 + OCR / 文字定位

2. **graph builder 加 PDF 楼梯检测**
   - 解锁 5 张 STAIR_PENDING 规则
   - 难点：楼梯多边形识别 + tread/riser/well/handrail 数据从平面图或剖面图绑定
   - 依赖：vision/CV + 几何约束推理

3. **真实图纸鲁棒性测试**
   - 当前 sample_clean.pdf 是 3.6 KB toy demo
   - 实际项目图纸几十 MB，多页 + 多比例 + 多种规范图签
   - builder 在真实 noise 下的失败模式未测

### 中 ROI（提升用户体验）

4. **Door / Stair schema 加 subtype 字段**
   - door_kind ∈ {auto, swing, sliding, folding}：让 RC-ACCESSIBLE-DOOR-WIDTH 拆 0.80/1.00 严格分支（当前是 reminder 妥协）
   - Stair.single_side_handrail / Stair.serves_floors_under_7：让 RC-STAIR-FLIGHT-WIDTH-1.10 升级为硬规则（含 1.00m 例外）

5. **ProjectMeta 自动从图签抽取**
   - 现在 ProjectMeta 来自 `--project-meta` YAML 手填
   - 自动从图纸首页图签抽 building_type / height_class / floors

### 大工程（产品形态）

6. **Web 上传界面 + 审图 worker**
   - 当前 archkg 是 CLI only
   - 需要：上传服务、异步任务队列、报告网页化、复核协作

7. **审图工作流支持人审注释回写**
   - feedback recorder 已在 — Reviewer 在 report.md 标 status=confirmed 后跑 `archkg feedback --apply`，已确认违规自动入库 test_cases
   - 体验：复核界面化 + 减少手工编辑 markdown

## 给现在想用的人的指引

如果想**今天就用**：
- 用例：审住宅平面图，重点看户门尺寸 / 走廊宽度 / 卧室面积 / 净高 / 地下室用途
- 步骤：填 ProjectMeta + Room Schedule YAML → `archkg review --project-meta meta.yaml --room-schedule schedule.yaml plan.pdf`
- 期望：6 + 4（如果 schedule 命中违规）个左右 error 级违规自动发现 + 17 项人工核对清单
- 不要期望：楼梯类（Phase 19+）、户门 subtype、PDF 自动抽净高/楼层（Phase 20+）

如果想**等 production-ready**：
- 关注 Phase 18+ 路线（见上文「走到真自动审批还需要什么」）
- 当 `archkg clause readiness` 显示 AUTODETECTABLE ≥ 20 张时，就是 Phase 18 真完成的信号

## 状态查询

```bash
archkg clause readiness     # 各 tier 分布 + 逐条详情
archkg clause coverage      # 30/30 标准条款覆盖
archkg clause fidelity      # 数值保真闸 0 errors
archkg clause verbatim      # paraphrase clause 与 PDF 原文对照
archkg demo --meta          # 端到端 demo（包括样例 ProjectMeta）
```
