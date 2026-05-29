# P32 智能审图软件调研与开发指引

调研日期: 2026-04-28

## 目的

本调研用于指导 ArchReview-KG 后续开发, 重点回答三件事:

- 现有优秀智能审图/自动合规产品已经解决了什么。
- 哪些能力应复用开放标准或成熟工作流, 不应从零重造。
- ArchReview-KG 下一阶段应怎样把“识别图纸内容”推进到可复核的闭环。

事实边界:

- 代码真相仍以本仓库为准; 本文是开发参考, 不是能力承诺。
- 当前 ArchReview-KG 的强项是 PDF/栅格输入、实体图谱、规则卡、证据报告、benchmark 和人工复核闭环。
- 本文不把任何 AI / VLM / LLM 输出视作最终合规判定。合规结论必须落在可追踪的实体、尺寸、条文和人工复核状态上。

## 一句话结论

成熟路径不是“让模型看图后直接说合规/违规”, 而是:

1. 先把图纸/BIM 转成可验证的数据层。
2. 再把规范拆成可执行或可核查的规则输入需求。
3. 对每个结论输出证据、位置、条文、置信度和复核状态。
4. 用 issue lifecycle 把发现、修正、再审查串成闭环。

ArchReview-KG 当前 P24-P31 的方向是正确的: `drawing_understanding.json`、expected inventory、real-plan known_gap、sheet-region/title-block 裁剪, 都是在补“规则运行前的数据可信度”。P32 后应优先补 rule-input readiness、sheet 区域自动候选、BCF-like issue 生命周期和 IFC/IDS 旁路, 而不是急着扩大规则数量或直接承诺复杂图纸全自动审查。

## 生态地图

### 1. BIM/IFC 模型检查器

代表:

- Solibri: BIM QA、clash/code compliance、component property checks、custom rules。
- BIMcollab Zoom: IFC/IDS 检查、BCF issue 管理。
- CORENET X / IFC+SG: 政府级 BIM 报审, 通过 IFC+SG 参数和模型质量要求降低审查不确定性。
- IfcOpenShell / IfcTester: 开源 IDS 读写、IFC against IDS 校验和报告输出。

可借鉴:

- 先定义模型/数据交付要求, 再做合规检查。
- 检查结果不是一句话, 而是 rule -> applicable elements -> requirement -> actual value -> issue。
- issue 可以变成 BCF topic, 带位置、状态、责任、讨论和关闭记录。

不应照抄:

- 直接把 ArchReview-KG 做成 Solibri 克隆。当前项目的差异化是从 PDF/栅格图纸进入证据图谱, 这是 BIM checker 没有直接覆盖的入口。

### 2. 开放标准与开源工具

代表:

- buildingSMART IDS: 机器可读的信息交付要求, 用于检查 IFC 模型是否满足对象、分类、属性和值要求。
- buildingSMART bSDD: 标准化术语/属性词典, 可作为 IDS 中属性名和概念名的来源。
- buildingSMART BCF: 模型问题沟通和状态跟踪标准。
- IfcOpenShell IfcTester: 可直接验证 IFC 与 IDS, 可作为未来 IFC lane 的依赖。

可借鉴:

- `rule-input readiness` 应像 IDS 一样显式声明“规则需要哪些实体/属性/单位/值域”。
- ArchReview-KG 的 issue schema 后续应支持 BCF-like 字段: viewpoint/bbox、referenced components、status、assignee/reviewer、resolution note、superseded-by-run。
- 对 IFC 输入不要手写一套完整 BIM 校验器; 应先接 IfcOpenShell/IfcTester 做 proof-of-value。

### 3. PDF/CAD/BIM AI permit review

代表:

- Archistar eCheck: 面向政府/申请方的电子报建预审, 支持 PDF/CAD/BIM, 以本地规则数字化为基础生成预审结果。
- Vancouver eCheck pilot: 使用 Archistar 技术做提交前合规反馈, 同时明确结果是信息性指导, 不等于许可批准。
- PermitGuard / CodeComply.Ai / PlanCheckPro.AI / CivCheck 等: 2025-2026 年快速出现的 AI plan review 产品, 共同卖点是 PDF plan set 上传、多专业 review、code citations、confidence/risk report。

可借鉴:

- PDF/CAD/BIM 多输入是行业趋势, 但“提交前预审”和“正式审批”边界必须写清。
- 用户体验应围绕“哪些图纸已读、哪些字段缺失、哪些问题可复核、如何改后重跑”设计, 而不是单页聊天。
- 对 AI review 产品的供应商声明要保持审慎; 真正可落地的是 sheet classification、discipline splitting、code citation、confidence/risk report、human authority retained。

不应照抄:

- 不要把 LLM 输出直接写成 `Issue(severity=error)`。
- 不要在没有 jurisdiction-specific rule pack、输入质量校验和人工 authority 的情况下声明“自动审批”。

### 4. 生成式/早期设计工具

代表:

- Autodesk Forma: 早期 site planning / schematic design, 用 AI-powered analysis 和 design automation 支持方案探索。
- Augmenta: 面向施工级 MEP/电气布线自动化, 用 Revit/规则/协调约束生成可审阅的模型。
- TestFit / 类似工具: 面向可行性、场地、户型/体量快速迭代。

可借鉴:

- 早期方案工具更关注生成和快速反馈, 与施工图审查不是同一层。
- 自动设计产品仍保留 review/adjust, 并让输入标准、间距、clearance、routing preference 显式化。
- 对 ArchReview-KG, 这类工具的启发是“规则输入要可配置, 输出要可迭代”, 不是现在转向生成设计。

### 5. 中国 BIM 智能审图实践

代表:

- 广联达 BIM 施工图智能审查系统: 二三维联合审查, 面向行管部门、BIM 模型质量和设计质量。
- 广联达数字化审图系统: 更偏流程/监管/在线审查平台, 北京等地有 AI 审图试点描述。
- 南京市建筑工程施工图 BIM 智能审查技术导则: 明确 BIM 智能审查是基于施工图信息模型, 覆盖可量化条文, 且遵循“人审机辅”。

可借鉴:

- 国内政府级路线强调二三维联合、模型交付标准、图模一致性、可量化条文和人审机辅。
- “可量化条文”应成为 ArchReview-KG rule-card readiness 的核心分类。
- 国内路线不是 PDF-only 奇迹, 而是平台、交付标准、模型质量和人工审查共同构成。

## 产品/能力矩阵

| 类别 | 代表 | 输入 | 核心能力 | ArchReview-KG 可复用经验 | 避免事项 |
| --- | --- | --- | --- | --- | --- |
| BIM 模型检查 | Solibri | IFC/BIM | 规则检查、clash、属性校验、自定义规则 | rule library + issue result + component evidence | 不做闭源 BIM checker 克隆 |
| IDS 校验 | buildingSMART IDS / IfcTester | IFC + IDS | 信息交付需求校验 | 建 rule-input readiness; 未来接 IFC lane | 不手写完整 IFC 标准栈 |
| BIM issue 协作 | BCF / BIMcollab | IFC + issue topics | issue status、viewpoint、协作 | 后续 issue lifecycle/export | 不把 issue 当一次性 JSON |
| 政府 BIM 报审 | CORENET X / IFC+SG | IFC+SG + 2D 补充 | 模型质量、参数映射、合规网关 | 输入质量门、模型交付标准 | 不忽略输入质量就跑规则 |
| AI permit precheck | Archistar eCheck / Vancouver eCheck | PDF/CAD/BIM | 预审、规则数字化、报告 | 上传-反馈-修正-重跑闭环 | 不声称预审等于许可批准 |
| AI plan review 初创 | PermitGuard / CodeComply / PlanCheckPro / CivCheck | PDF plan set | 多专业 agent、code citation、risk report | sheet classification、confidence、citation UX | 不把 vendor claim 当验收事实 |
| 生成式方案 | Forma / TestFit | site/massing/project data | 快速方案和分析 | 参数化、可迭代反馈 | 不转向生成设计主线 |
| 自动施工建模 | Augmenta | Revit/model/schedules | 规则化生成、clash-free routing | 输入标准显式化、review/adjust | 不混淆“生成可施工模型”和“审图” |

## 对 ArchReview-KG 的开发决策

### 应立即吸收的设计

1. Rule-input readiness
   - 每张规则卡声明需要哪些输入: entity type、geometry、dimension、label、project meta、schedule、sheet region、source confidence。
   - 每次 run 输出规则输入状态: `ready / missing_input / low_confidence / manual_only / not_applicable`。
   - 这比继续堆规则更重要, 因为它告诉用户“为什么这张图还不能被可靠审”。

2. Source-classified drawing evidence
   - 继续区分 design region、title block、schedule、legend、detail/callout、noise。
   - P31 的 sheet-region/title-block 裁剪应继续扩成候选建议, 默认不自动丢弃内容。

3. Issue lifecycle
   - issue 不只包含 rule_id 和 bbox, 还应有 `status`, `reviewer_decision`, `resolution_note`, `source_run_id`, `superseded_by_run_id`。
   - 后续可导出 BCF-like JSON/BCFZip, 或至少先做本地 issue history。

4. IFC/IDS side lane
   - 新增独立实验 lane: `archkg ifc validate --ifc model.ifc --ids spec.ids`。
   - 初期只调用 IfcOpenShell/IfcTester, 输出报告并映射到 ArchReview-KG issue schema。
   - 不与 PDF graph builder 混在一起, 先证明互补价值。

5. AI as assistant, not judge
   - LLM/VLM 可用于: sheet classification 候选、title-block 字段草案、rule-card authoring 草案、code citation 摘要、review note 草稿。
   - LLM/VLM 不可用于: 直接生成最终 violation, 直接覆盖 graph 实体, 直接修改 benchmark expected inventory。

### 当前不做的事

- 不做 Solibri/BIMcollab 的完整替代品。
- 不做“上传任意复杂施工图即可自动审批”的产品声明。
- 不把随机生成图或单个真实图纸 known_gap 当作能力通过证明。
- 不把 OCR 准确率、VLM 识图准确率写成承诺。
- 不跳过人工 expected inventory, 也不让模型自己生成 ground truth。

## P32 之后建议路线

### P33: Rule-input readiness dashboard

目标:

- 给每张规则输出输入可用性和缺失原因。
- Studio/viewer 中新增 readiness 面板。
- 报告中把“不触发”区分为 not applicable、missing input、low confidence、manual-only。

验收:

- 至少覆盖现有 32 张规则。
- 不改变现有 issue 生成逻辑。
- 有测试锁定 missing input 不会伪装成 pass。

### P34: Sheet-region 自动候选建议

目标:

- 在 P31 `--sheet-region` 手动裁剪基础上, 输出候选 design/title/schedule/legend 区域。
- 默认只提示, 不自动裁剪。

验收:

- 复杂样本能输出候选 bbox 和证据摘要。
- 用户确认或 benchmark expected 明确后才进入 graph。

### P35: Issue lifecycle / review state

目标:

- 给 issues 加 review lifecycle 字段。
- 支持从人工复核状态回写, 记录 confirmed / rejected / needs_info。
- 为后续 BCF export 做字段准备。

验收:

- 旧 issues.json 可兼容读取。
- 新 issue state 不影响规则引擎判定。

### P36: IFC/IDS spike

目标:

- 用 IfcOpenShell/IfcTester 增加独立 IFC validation lane。
- 把 IDS failure 映射成 ArchReview-KG issue-like report。

验收:

- 有最小 IFC + IDS fixture。
- 不引入对 PDF pipeline 的耦合。

### P37: Code-citation assistant / rule-card authoring helper

目标:

- 对规范条文做引用定位、rule-card 草案、解释摘要。
- 明确 `draft / reviewed / active` 状态。

验收:

- LLM 产物默认 draft。
- 人工确认前不进入 active rule_cards。

## 对复杂真实图纸能力的判断

以 2026-04-28 当前仓库能力看:

- 可以跑闭环: 上传/解析/图纸理解摘要/benchmark/报告/known_gap。
- 可以开始系统性处理复杂图纸: 通过 sheet-region、expected inventory、known_gap 逐步压缩失败面。
- 还不能声称“能可靠识别任意复杂真实建筑施工图的所有部件和尺寸”。

要达到用户提出的“能认出这张图在设计什么、每个部件是什么、尺寸如何”, 下一阶段关键不是先扩规范纠错, 而是:

1. 提升 sheet segmentation。
2. 扩 expected inventory 数量和类别。
3. 把每个识别结果与来源区域、证据类型和置信度绑定。
4. 建 readiness dashboard, 让规则知道自己缺什么。

## 来源索引

- Solibri Intelligent Model Checking: https://www.solibri.com/intelligent-model-checking
- Solibri / AcePLP / BCA Accessibility Compliance Checker beta: https://www.solibri.com/articles/solibri-and-aceplp-advance-digital-building-compliance-in-singapore-with-the-compliance-checker-for-accessibility
- buildingSMART IDS: https://www.buildingsmart.org/standards/bsi-standards/information-delivery-specification-ids/
- buildingSMART BCF: https://www.buildingsmart.org/standards/bsi-standards/bim-collaboration-format/
- IfcOpenShell IfcTester: https://docs.ifcopenshell.org/ifctester.html
- BIMcollab IDS validation workflow: https://helpcenter.bimcollab.com/en/articles/340833-performing-ids-property-validation-checks-in-bimcollab-zoom
- CORENET X IFC+SG model quality: https://info.corenet.gov.sg/ifc-sg/model-setup-and-coordination/essential-points-for-model-quality
- UpCodes Copilot intro: https://support.up.codes/support/solutions/articles/63000277619-intro-to-copilot
- City of Vancouver eCheck pilot: https://vancouver.ca/home-property-development/echeck-compliance-made-easy.aspx
- Archistar eCheck: https://www.archistar.ai/en-us/echeck/
- Autodesk Forma Site Design: https://www.autodesk.com/products/forma/overview
- TestFit Site Solver: https://www.testfit.io/product/generative-design
- Augmenta electrical automation: https://www.augmenta.ai/electrical
- 广联达 BIM 施工图智能审查系统: https://www.glodon.com/product/356
- 广联达数字化审图系统: https://www.glodon.com/product/357
- 南京市建筑工程施工图 BIM 智能审查技术导则: https://www.njkcsj.com/uploadfile/image/20210126/20210126145908497.pdf
- Automated code compliance checking research based on BIM and knowledge graph: https://www.nature.com/articles/s41598-023-34342-1
- PermitGuard AI plan review: https://www.permitguard.ai/
- CivicPlus / CodeComply.Ai announcement: https://www.civicplus.com/news/nn/civicplus-brings-ai-building-plan-review-codecomply-ai/
- PlanCheckPro.AI: https://plancheckpro.ai/
- CivCheck: https://www.civcheck.ai/
