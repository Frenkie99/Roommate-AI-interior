# 外部阅读沉淀（Readings）

> 用途：把外部高质量评测文章**提炼 + 适配 + 冲突标注**后沉淀于此，当作弹药库。
> 与 `METHODOLOGY.md` 的分工：本册是**缓冲层**（原汁提炼 + 本项目翻译），只有真正能升级顶层哲学的洞见才回写 METHODOLOGY，并注明出处。
> 阅读纪律（对齐 METHODOLOGY 第 7 节）：**带审视读，不当传声筒**。高阅读量 ≠ 适配本项目——这些文章绝大多数面向「Agent / 文本 trace / 训模型」团队，
> 而我们是「图像生成 + 不训权重 + 只调 prompt/编排」。凡不适用处，本册显式标注「⚠️不适用/需翻译」，不无脑收录。

---

## 0. 来源总览

| # | 来源 | 类型 | 抓取状态 |
|---|---|---|---|
| A | Anthropic《Demystifying evals for AI agents》 | 工程长文 | ✅ 全文 |
| B | Hamel《Your AI Product Needs Evals》 | 博客（评测三层级） | ✅ 全文 |
| C | Hamel《Creating a LLM-as-a-Judge That Drives Business Results》 | 博客（Judge 七步法） | ✅ 全文 |
| D | Hamel《A Field Guide to Rapidly Improving AI Products》 | 博客（错误分析为核心） | ✅ 全文 |
| E | Hamel《FAQ About AI Evals》 | 博客（大量实操 Q&A） | ✅ 全文 |
| F | Hamel《The Revenge of the Data Scientist》 | 博客（五大坑） | ✅ 全文 |
| G | Hamel《Inspect AI》 | OSS 工具介绍 | ✅ 全文 |
| H | Hamel《Evals Flashcards》 | 卡片（13 张） | ⚠️ 正文在图片里，仅取到 13 个主题，逐卡内容未抓到 |
| — | 合集内 3 个 YouTube（错误分析实操 / 领域评测系统 / 工程师 PM 协作） | 视频 | ⚠️ 非文本，未抓取；要点多与 B/C/D/E 重合 |

> **图像评测专题另立一册**：AI 图像产品如何评测、VLM-as-judge 是否值得花钱、VQA vs 成对、结构维怎么评 →
> 见 `RESEARCH_IMAGE_EVAL.md`（2026-06-30 深度研究，27 来源/对抗式核实），已据其修正 `VISION_JUDGE_DESIGN.md` 第 7 节。

来源页：Anthropic 单篇 + `hamel.dev/notes/llm/evals/` 合集（11 项，已逐项甄别）。

---

## 1. 跨来源共识（最该内化的部分）

把 8 个来源里**反复出现、彼此印证**的硬核原则收敛成下面 9 条。每条后面直接给「本项目落点」。

1. **「永远先看数据」(Look at your data) 是 ROI 最高的活动，且最常被跳过。**（A/D/F 一致）
   - 错误分析（error analysis）= 系统性读真实失败样本 → 归类失败模式 → 据此才决定测什么。**不是先建指标，是先读数据让指标涌现。**
   - 本项目落点：对应**模块四（人工分析）**。我们已有「失败地图」，但做法是 top-down（按 metadata 切片），文章要求 **bottom-up 开放编码**（见下「审慎挑战 1」）。

2. **二元 Pass/Fail + 书面 critique，胜过 1-5 Likert 量表。**（B/C/D/E/F 几乎篇篇强调）
   - 理由：Likert「3 和 4 差在哪没人说得清」，不同标注者标尺不一，给假精度（4.2→4.3 像在进步），且与业务价值不挂钩。二元逼你想清「到底什么算成功」。
   - critique（两句话理由）才是金矿：既是 few-shot 素材，又**在书写过程中倒逼标准显性化**（criteria drift，见第 4 条）。
   - 本项目落点：⚠️**与我们现状有张力**（我们用 1-5 四维 Likert 金标准）——见「审慎挑战 2」，需分场景看。

3. **LLM-as-Judge 必须当分类器来验证，不能裸用。**（A/C/E/F 一致，F 说得最狠）
   - 核心动作：拿人工标签做 **train/dev/test 切分**，在 dev 上「爬山」调 Judge 的 prompt，在留出 test 上报 **precision/recall（不是 accuracy）**——类别不平衡时 accuracy 会骗人。
   - Judge prompt 要放 **3-5 个带完整上下文的专家示例**；目标对齐度 >90%，通常 2-4 轮 prompt 迭代达到。
   - **✅ 强力印证我们正在做的事**：我们的视觉 Judge DoD = 「vs 85 条金标准算相关、达标才采用」正是「把 Judge 当分类器验证」；上一轮加的 **few-shot 锚定 = 文章的「3-5 专家示例」**；**留出（验证样本≠锚点）= train/test 切分防泄漏**。我们走在正道上。

4. **评测标准无法预先写死，是在「看输出」过程中长出来的（Criteria Drift）。**（C/D/F，引 Shankar et al.）
   - 推论：必须先标一批数据、再写 Judge prompt；指望开工前就定好 rubric 是幻觉。
   - **✅ 印证**：我们先标满 85 条金标准、再设计视觉 Judge，顺序正确。

5. **单一「仁慈独裁者」领域专家定标，而非多人投票求共识。**（C/D/E）
   - 一个有领域判断力的人当唯一裁判，消除标注冲突与组织瘫痪；多标注者才需算 Cohen's Kappa 一致性。
   - **✅ 印证**：frenkie 一人标满 85 条 = 单一领域专家定标，合规。

6. **自建领域专属数据查看器，是 ROI 最高的基建（号称让迭代快 ~10x）。**（B/D/E）
   - 通用看板/通用指标反而有害（制造「在进步」的假象、分散注意、漏掉领域特有失败）。
   - **✅ 印证**：我们的 Streamlit 看板（原图/效果图并排 + 切片 + 可信度面板）正是此物。

7. **合成数据：只生成「用户输入」、灌进真实系统拿真实输出；且两步走（先结构化维度元组 → 再转自然语言）避免雷同。真实数据为主。**（B/C/D/E）
   - 本项目落点：**模块一（数据集）**。我们候选图是真实毛坯照片（✅ 符合「真实为主」）；路径B 采难 case 时套用「维度元组→NL」两步法。

8. **分层防护（Swiss Cheese）：自动评测 + 生产监控 + 人工读 trace，没有单层能兜住所有问题。**（A）
   - 还有「能力评测 vs 回归评测」二分（见 A 篇精炼）——这是我们目前**缺的框架**。

9. **评测的产出是「迭代闭环」，不是分数报告；60-80% 精力应花在错误分析/看数据，而非搭自动检查器。**（A/D/E/F）
   - ⚠️**对我们是当头棒喝**：我们在「模块三 搭评分器」上投入很重，而**模块五（迭代优化）几乎为零**。见「审慎挑战 3」。

---

## 2. 逐篇精炼

### A. Anthropic《Demystifying evals for AI agents》
- **核心**：评测是「自信地规模化上线 Agent」的基础设施，价值随生命周期复利。
- **最有价值的新框架（我们目前没有的）**：
  - **能力评测(capability) vs 回归评测(regression)**：能力评测起点低分、专挑做不好的、给「可攀登的山」；回归评测维持~100% 防退步。成熟的能力评测「毕业」转为回归套件持续跑。
  - **pass@k / pass^k**：应对非确定性。pass@k=k 次至少一次对（找到一个解就行的场景）；pass^k=k 次全对（面向用户、要求每次都稳）。
  - **Grade outcomes, not paths**：评最终结果而非路径——Agent 会用你没预料到的有效解法，按路径罚分是浪费。
  - **0% 通过率通常是任务坏了，不是模型菜**；**100% 通过率=已饱和**，只能防回归、不再有信号。
  - **Swiss Cheese 分层**、**任务要无歧义（领域专家独立判都得同样结论）**、**留参考解证明任务可解**、**正负样本均衡**、**环境隔离（每次干净起点）**。
- **本项目关联适配**：
  - 「能力 vs 回归」直接可用：我们 85 条目前混在一起，应区分——哪些当「能力靶子」（模型现在就烂的难 case，对应路径B），哪些当「回归基线」（已稳的，防改 prompt 改崩）。
  - 「grade outcomes not paths」对图像天然成立：我们评的就是最终图，不评生成路径。
  - pass^k 对「面向用户要每次都稳」很关键——但我们当前每个输入只生成一张图、未测同输入多次生成的方差，是个缺口（优先级中）。
- **与现有方法论关系**：**补充**（METHODOLOGY 没有「能力/回归」「pass@k/pass^k」「饱和度」这几个概念，值得回写）。

### B. Hamel《Your AI Product Needs Evals》
- **核心**：成功=迭代速度，迭代速度=评测+调试+改行为三件套形成的飞轮。
- **评测三层级（重要骨架）**：
  - **Level 1 单元测试**：把能力拆成 feature×scenario，每格写断言（如 `len(listing)==0`）；LLM 批量造测试输入；每次提交都跑（CI）。低成本高频。
  - **Level 2 人工&模型评测**：记录 trace → 自建轻量查看器读 trace → LLM critique 当**第二层**（不是替代人）；量化「模型分 vs 人工分」相关性，**分别报 precision/recall**。中成本中频。
  - **Level 3 A/B 测试**：成熟产品才上，测真实用户行为。高成本低频。
- **金句**：「Success with AI hinges on how fast you can iterate.」「You can never stop looking at data—no free lunch.」「Pass rate is a business decision, not a technical constraint.」
- **本项目关联适配**：
  - Level 1 单元测试对图像生成**部分适用**：可对「结构是否保留」做代码断言（我们的 structural_fidelity 就接近此物），但「美学/指令」无法写死断言→只能走 Level 2 视觉 Judge。
  - Level 2 = 我们当前主战场（金标准 + 可信度 + 视觉 Judge）。
  - ⚠️**翻译**：原文 Level 1 偏文本/结构化输出断言，我们图像场景的 Level 1 比重天然小，别强行套。
- **与现有方法论关系**：**补充**（三层级是清晰的执行骨架，可回写 ROADMAP/METHODOLOGY 当分层参照）。

### C. Hamel《Creating a LLM-as-a-Judge》（七步「Critique Shadowing」）
- **核心**：「不是 Judge 本身创造价值，而是它逼你认真看数据。」（"a nice hack I use to trick people into looking at their data."）
- **七步**：(1) 找唯一领域专家 →(2) 造跨 feature/scenario/persona 的多样数据 →(3) 专家做**二元 Pass/Fail + 详细 critique** →(4) 先修明显错误 →(5) 迭代建 Judge（放 3-5 专家示例，2-4 轮调到 >90% 一致）→(6) 在**未见过的数据**上做错误分析、按根因归类 →(7) 必要时才造专项 Judge。
- **关键**：二元>Likert；agreement 类别不平衡时拆 precision/recall；判 Judge 该用「你预算内最强的模型」（Judge 预算≠生产预算）。
- **本项目关联适配**：**这篇几乎是我们视觉 Judge 的施工图**。
  - ✅ 我们已做：单一专家(frenkie)、先标后建、few-shot 锚定、留出验证。
  - ⏳ 我们还没做：第(6)步「在未见数据上按根因归类错误分析」——这正是模块四该深化的方向。
  - ⚠️ 张力：第(3)步要二元 Pass/Fail，我们用的是 1-5。见「审慎挑战 2」。
- **与现有方法论关系**：**强印证 + 补充**（七步法可作为视觉 Judge 实施的检查清单回写 VISION_JUDGE_DESIGN）。

### D. Hamel《Field Guide to Rapidly Improving AI Products》
- **核心**：赢家痴迷于「测量与迭代」而非工具与框架；错误分析是 ROI 最高的活动。
- **要点**：错误分析（开放观察→涌现失败分类，某案例 3 个问题占 60%+ 失败）；自建数据查看器；**让领域专家直接写 prompt**（"Prompts are just English"）；按「实验节奏」而非「功能日期」排路线图（capability funnel + 2 周可行性 + 1 月技术验证）。
- **常见错误**：工具陷阱、通用指标痴迷、跳过错误分析、看门人模式（工程师把专家 PPT 翻成 prompt）、过度信任自动评测。
- **本项目关联适配**：
  - 「capability funnel + 实验节奏路线图」可直接给我们的 ROADMAP 补一个视角：把模块五的迭代按「2 周一个实验 + 明确 pivot 点」组织。
  - 「领域专家直接写 prompt」对我们：frenkie 应能直接改后端生成 prompt 并复测，而非隔层传话——这是打通模块五的组织手段。
- **与现有方法论关系**：**印证**（与 METHODOLOGY 第 1 节「北极星=迭代闭环」「Look at your data」高度同源）。

### E. Hamel《FAQ About AI Evals》（最厚的实操弹药库）
- **高价值 Q&A 摘要**：
  - **MVP 评测**：改动大时读 20-50 条输出；指定一个「仁慈独裁者」；用 notebook/简易自建界面即可，别先上重基建。
  - **预算**：评测不是单列项，60-80% 精力在错误分析而非搭自动检查。
  - **错误分析方法**：开放编码(open coding，自己读 trace 写观察) → 轴心编码(axial coding，归类) → 迭代到「理论饱和」（~100 条 trace，读到不再冒新类别）。**开放编码绝不可外包/自动化**。
  - **不要做 eval-driven development（普遍意义上）**：LLM 失败面无限，写「发现的错误」的评测，不写「想象的错误」。例外：明确约束（「绝不提竞品」）可以预先写。
  - **不要给每个失败都建自动评测器**：LLM-Judge 要 100+ 标注、有维护成本，只给「反复迭代的持续性泛化失败」建。
  - **相似度指标(BERTScore/ROUGE) 对多数应用没用**；对 RAG 检索/搜索推荐才有用。
  - **同模型既做主任务又做评委通常 OK**（Judge 是不同任务），关键看与人工对齐度。
  - **CI/CD 评测 vs 生产监控**：CI 用小而精的策划集（100+，favor 断言省成本）；生产异步采样、靠 reference-free 的 LLM-Judge、追置信区间下界。
  - **Guardrails vs Evaluators**：护栏=同步、毫秒级、确定性、拦 PII/脏话；评测器=异步、测主观质量、喂仪表盘不拦答案。
  - **RAG 评测**：检索(用 Recall@k/Precision@k/MRR) 与生成(错误分析+人工+对齐的 Judge)**分开评**；引 Jason Liu「只有 6 种 RAG 评测」。
  - **多轮/Agent**：先整体 Pass/Fail 看是否达成用户目标 → 盯「第一处上游失败」（下游常是级联）→ 用「状态转移失败矩阵」找热点。
- **本项目关联适配**：
  - 「不要 eval-driven development、写发现的错误」⚠️**与 A 篇 Anthropic 的「能力评测先于能力建立」有张力**——两者都对，区别在：Anthropic 面向「赌未来模型能力」的前瞻靶子，Hamel 面向「别凭空想象失败」。我们取中：**主力评测来自错误分析（已发现的失败），少量当能力靶子（路径B 难 case）**。
  - RAG 那段对本项目有第二落点：项目用了 DeepSeek RAG，若日后评 RAG 子系统，检索/生成分开评 + IR 指标可直接用。
  - 「open coding 不可自动化」= 给模块四定了红线：失败模式得 frenkie 亲自读图归纳，别让我（AI）代劳归类。
- **与现有方法论关系**：**补充**（大量可操作细则，留在本册当查询手册，不必全搬进 METHODOLOGY）。

### F. Hamel《The Revenge of the Data Scientist》（五大坑）
- **核心**：「The harness is data science.」训模型从不是主体，评测харness 才是数据科学的活；LLM 时代数据科学家不仅没过时，反而是命门。
- **五坑 → 数据科学解药**：(1) 通用指标 → 探索性分析读 trace 归类；(2) 未验证的 Judge → 当分类器、train/dev/test、报 precision/recall；(3) 坏实验设计 → 合成数据扎根生产日志、Likert 换二元；(4) 坏数据标签 → 领域专家亲自标、把标注当「需求收集」；(5) 过度自动化 → 保留人对「什么重要」的判断。
- **金句**：「Likert scales hide ambiguity and kick the can down the road.」「None of this is new. The names changed, the work did not.」
- **本项目关联适配**：**这篇是我们方法论第 8 节「实证案例」的同盟军**——我们用 85 条证伪 3 个评分器，正是「把 Judge 当分类器验证 + 拒绝通用指标(clip)」。可在面试叙事里引「the harness is data science」。
- **与现有方法论关系**：**强印证**（与 METHODOLOGY 第 3 节「可信度准则」、第 8 节几乎同构）。

### G. Hamel《Inspect AI》（OSS 工具）
- **是什么**：UK AISI 的 JJ Allaire 主导的开源 Python 评测框架，Anthropic/DeepMind 等在用。
- **三抽象**：**Dataset**(输入+目标) / **Solver**(怎么让模型产出，可链式/agentic) / **Scorer**(对照目标打分，支持模式匹配/LLM-judge/自定义)。强在可复现日志、异步并行、可组合、富观测、沙箱。
- **本项目关联适配**：⚠️**暂不引入**。我们 evals/ 已自建 registry/runner/result_store/scorer 体系，概念上与 Inspect 的 Dataset/Solver/Scorer 同构。引入它=重写基建，当前 ROI 低。**价值在「借它的抽象命名校准我们自己的设计」**：我们的 scorer ≈ Scorer，runner ≈ harness，metadata ≈ Dataset。若日后要规模化/对外可复现，再评估迁移。
- **与现有方法论关系**：**参考**（工具，不进哲学；记此条避免日后重复造轮子时忘了它的存在）。

### H. Evals Flashcards（未抓全）
- 仅取到 13 张卡的主题：错误分析 / 何时写 eval / 通用指标 / 常见错误 / 自动评测类型 / Likert / 信任 LLM Judge / 采样 trace / 合成数据 / trace 用于 eval / 转移矩阵 / 部署 eval。
- 逐卡正文在图片里，本次未抓到。主题与 B-F 高度重合，**不构成新信息缺口**。若日后要逐卡内容，需 OCR 图片或访问课程。

---

## 3. 对本项目现状的「审慎挑战」（最该让 frenkie 看的部分）

读完这些权威材料，对照我们当前做法，有四处值得你停下来想：

**挑战 1：我们的「失败地图」是 top-down 切片，文章要的是 bottom-up 开放编码。**
- 我们路径A 是「按 room_type / 难度反推 difficulty 切片」——这是**先有分类、再套数据**。
- 文章（D/E/C）一致要求：**先一条条读 bad case，写开放观察(open coding)，再让分类从数据里涌现(axial coding)**，读到「理论饱和」。
- 差距：我们还没做过一轮真正的「读图→写观察→归纳失败模式分类」。这是模块四下一步最实的活，且**红线：open coding 必须 frenkie 亲自做，不能让 AI 代归类**。

**挑战 2：金标准用 1-5 Likert，而文章几乎篇篇主张二元 Pass/Fail + critique。**
- 张力是真的，但**不是非黑即白**：
  - 我们用 Likert 是为了**度量评分器可信度**——算 Spearman 需要序数方差，二元会损失区分度。**这个用途上 Likert 是对的**（甚至必要）。
  - 但文章的洞见仍刺中我们：**我们的金标准只有分数、没有 critique（书面理由）**。缺了 critique = 缺了 few-shot 素材、缺了「标准显性化」、缺了错误分析的原料。
- 建议（不推翻已有）：下一轮人工分析时，**给每条（或失败的那些）补一句二元判定 + 两句话 critique**，与现有 1-5 分并存。Likert 喂可信度计算，二元+critique 喂错误分析与 Judge few-shot。

**挑战 3：我们重「模块三搭评分器」，文章说 60-80% 精力该在「模块四看数据 + 模块五迭代」。**
- F/D/A/E 反复讲：评测的产出是**迭代闭环**，不是评分器。我们模块三打磨很深，但**模块五至今为零**——从没用评测结果驱动过一次「改 prompt→复测涨分」。
- 这印证了我上一轮的建议：**哪怕只用唯一可信的 structural_fidelity，也该先手动跑通一次模块五闭环**，证明飞轮能转。

**挑战 4：缺「能力评测 vs 回归评测」的区分。**
- 我们 85 条混作一团。按 A 篇：应把「模型现在就烂、用来攀登」的当**能力评测**（≈路径B 难 case），把「已经稳、防改崩」的当**回归评测**（每次改 prompt 都跑）。这个区分能让模块五的迭代有明确的「攻什么、守什么」。

---

## 4. 可执行的增补清单（映射到五模块）

| 模块 | 来自阅读的增补动作 | 优先级 |
|---|---|---|
| 一 数据集 | 路径B 用「维度元组→NL」两步法造难 case；区分能力/回归两类 | 中（押后于视觉 Judge） |
| 三 grader | 视觉 Judge 实施对照 C 篇七步法清单；Judge 验收报 precision/recall（二元化后）而非只看相关 | 高（进行中） |
| 四 人工分析 | **做一轮真正的 open coding + axial coding**（frenkie 亲读 bad case）；金标准补「二元判定 + 两句 critique」 | 高（下一步主攻） |
| 五 迭代优化 | 用 structural_fidelity 先手动跑通一次「发现烂图→改 prompt→复测」闭环；按「2 周一实验 + pivot 点」组织 | 高（飞轮验证） |
| 跨模块 | 把「能力 vs 回归」「pass@k/pass^k」「饱和度」「Swiss Cheese 分层」补进方法论 | 已回写 METHODOLOGY 第 9 节 |

---

> 维护规则：日后再读新文章，在第 2 节加一篇「X.」小节（来源+核心+本项目关联+与现有方法论关系），
> 若产出能升级哲学的洞见，回写 METHODOLOGY 并在第 1 节共识表登记。**始终带审视读，冲突显式标注。**
