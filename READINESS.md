# ArchReview-KG 生产就绪度 (v1.0.0 / Phase 17)

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
| **PARTIAL_AUTODETECT** | 4 | 规则正确但需 builder 抽 entity properties | 卧室净高 < 2.40 m（净高来自剖面图，目前不抽） |
| **STAIR_PENDING** | 5 | 规则+引擎已就位，等 graph builder 加 PDF 楼梯检测 | 楼梯踏步 < 0.26 m / 踢面 > 0.175 m / 扶手 < 0.90 m |
| **REMINDER_BY_DESIGN** | 18 | severity=info，提供"人工核对清单"而非自动结论 | "项目为住宅，请核对外窗窗台 < 0.90 m 时是否设防护设施" |

**总计**: 4 + 1 + 4 + 5 + 18 = 32 张规则。**自动判定上限 = 4 + 1 = 5 张**（前提：ProjectMeta 填完整 + 户型/走廊/门尺寸标注准确）。

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

`out/report.md` 自动分两区：
- **违规清单**（6 项 / severity=error）：reviewer 必须逐条复核
- **人工核对提醒**（17 项 / severity=info）：reviewer 对照图纸自检

## "100% coverage" 真正含义

- ✅ 30 条国标都已建模为规则卡
- ✅ 规则 logic 都过 fidelity 闸 + Codex 审
- ✅ 引擎、feedback、verbatim audit、CLI、报告模板都已对齐
- ❌ 不等于 "上传任何图纸即自动产生通过/驳回结论"

把 v1.0 当作**规则知识库与引擎的完整态**，而非**生产可用审图服务**。

## 走到"真自动审批"还需要什么

按 ROI 排序：

### 高 ROI（解锁现有规则）

1. **graph builder 加 Room.properties 抽取**
   - 解锁 4 张 PARTIAL_AUTODETECT 规则
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
- 用例：审住宅平面图，重点看户门尺寸 / 走廊宽度 / 卧室面积
- 步骤：填 ProjectMeta YAML → `archkg review --project-meta meta.yaml plan.pdf`
- 期望：6 个左右 error 级违规自动发现 + 17 项人工核对清单
- **不要期望**：楼梯类、净高类、坡屋顶、地下室等条款自动判（这些等 Phase 18+）

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
