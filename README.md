# ArchReview-KG

> 民建图纸自动审图引擎 — 32 张 GB 国标规则卡 + 实体图谱构建器 + 对抗训练 lane

[![pytest](https://img.shields.io/badge/pytest-241%20passing-brightgreen)](#)
[![rules](https://img.shields.io/badge/rules-32%2F32%20covered-brightgreen)](#)
[![adversarial](https://img.shields.io/badge/F1-1.00%20on%20100--case%20battery-brightgreen)](#)
[![version](https://img.shields.io/badge/version-1.2.0-blue)](CHANGELOG.md)

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
archkg viewer -d out
```

`out/` 下会有：
- `annotated.pdf` — 标注红框 + 文字说明的 PDF
- `report.md` — 中文复核报告（违规清单 + 人工核对提醒分区）
- `issues.json` — 结构化问题清单（rule_id / bbox / severity / 证据）
- `entity_graph.json` — 抽出的实体图谱
- `index.html` — viewer 渲染的查阅页

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

archkg viewer -d out/
```

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

依赖：Python 3.11+ / Pydantic 2 / shapely / PyMuPDF / typer / Jinja2。可选
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
tests/                   241 pytest
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

# Clause fidelity 审计 (规则卡 vs 国标条款 numeric drift)
archkg clause fidelity

# Coverage tier 分布
archkg clause readiness
```

---

## 路线

完整 changelog 见 [CHANGELOG.md](CHANGELOG.md)。

**v1.1.x 候选方向**（按用户优先级排序）:
- FN auto-promote 基础设施（battery 出 FN 自动 codify 到 rule_cards.yaml test_cases）
- 真实 PDF robustness pass（CAD 多页、OCR 文字、varied scales）
- 继续加 rule 到 ~25 张（剩余多需 builder 出新 entity: balcony/window/railing）
- Web 上传界面 + 异步 worker（产品化方向）

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
