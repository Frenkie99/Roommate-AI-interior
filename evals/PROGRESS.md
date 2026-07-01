# 评测体系 进度 / 复盘日志

> 配套：`ROADMAP.md`（分阶段计划）· `METHODOLOGY.md`（哲学）· `DATASET.md`（数据自检）。
> **重启会话第一眼看本文件顶部「当前状态快照 + 下一步立即行动」即可续接。**
> 维护规则：每次会话结束前更新顶部快照，并在「会话日志」**最上方**新增一条（倒序）。

---

## 📍 当前状态快照

- **成熟度位置**：L1→L2 推进中。**已有第一个被数据证明可信的评分器**（structural_fidelity +0.418）。
- **当前阶段**：阶段 0 ✅ · 阶段 1 ✅ · 阶段 2 🟡（结构评分器抢救成功；clip+llm_judge+iou+fid 四个无效/桩评分器已全部退役；视觉 Judge 已设计待实施）· 阶段 3(评测集) 🟡（路径A完成：85 条已可切片+失败地图；路径B采新难case押后）。
- **看板现状**：概览/可信度只显示唯一可信指标 structural_fidelity（+0.418）。registry 现仅注册 structural_fidelity。clip/llm_judge 的数据列已从 eval_results 移除；iou/fid 本就无数据列。
- **评测集**：85 条已激活切片。**两个难度轴并存**：`intrinsic_difficulty`(内在难度，2026-06-30 看图判定 易17/中29/难30/极难9，脚本 `apply_intrinsic_difficulty.py`+标签 `intrinsic_difficulty_labels.json`) 与 `difficulty`(结果难度，从人工 overall 反推)。room_type 38/85(看图补到)+结构 tags 35/85。早期回填脚本 `enrich.py`(幂等)。失败地图见会话日志 2026-06-26。
- **环境**：本地 Mac（Apple Silicon arm64，系统 Python 3.9.6）。
  - venv：`evals/.venv`（已建）。
  - 轻量三件套：✅ streamlit 1.50.0 / pandas 2.3.3 / Pillow 11.3.0。
  - 结构评分依赖：✅ numpy 2.0.2 / opencv 4.13.0 / scikit-image 0.24.0。
  - torch/transformers：未装（仅 clip 需要，而 clip 已判弃用 → 预计不再装）。
- **看板**：✅ 可启动。命令见下方。冒烟测试通过（UI 全导入、85 对图加载、85/85 图片路径可显示）。
- **数据**：85 对真实评测图齐全；`eval_results.json` 含 85 条真实分（clip/structural_fidelity/llm_judge）。
- **金标准**：`gold_labels.json` 已存在，**85/85 全标完**（标注人 frenkie），四维度均用满 1-5、方差充足，是有效的真值尺。

## ⏭️ 下一步立即行动（2026-07-01 晚更新）

> **用户拍板节奏**：trace 相关本地代码先攒着**不 push**，等本地全搞好再**统一 push + 部署**。用户已 pivot 到**模块二（评测环境 / eval harness）**开始上网课学习。
> trace 管道：第3步(埋点)+第5步(导入)**本地代码已完成并本地测通**，只差①部署 ②第4步用户点评埋点（已降为待办）。

1. **【新主线】模块二 = 搭建评测环境 / eval harness**（用户正在学这节网课）。这是把"数据集 + 评分器 + 执行器 + 报告"串成一条能一键跑的流水线。**下次开工先跟用户对齐 harness 现状与缺口**（executor/ 已有骨架，需盘点）。
2. **【待办·后面再做】第4步 = 用户点评埋点（动前端）**：生成的效果图下面加按钮「满意/重新生成/下载/不要了」，用户一点就写进 trace 的 `feedback` 字段 = bad case 金矿；同时前端生成 `session_id` 回传后端（当前埋点 session_id 先留空）。用户已确认：**这是个独立埋点，先记着，后面搞**。
3. **【等用户操作·攒着一起来】部署 trace 到生产**：CI 已禁用(纯手工)。等本地都好了，统一 push → 服务器 `git pull` + 重启 `roommate-backend.service`。生效后每次真实用户成功生图 → 追加一条到 `backend/data/traces.jsonl`；之后用 `python -m evals.dataset.import_traces <拉回本地的traces.jsonl>` 导入评测集（幂等，只导入成功生图，缺图跳过）。可统计 `vision_analysis_ok` 量化"静默降级到盲DeepSeek"的真实频率。
3. **视觉 Judge 现状（半成品，待 trace 解锁）**：v2 已重写为 VQA(指令)+成对(美学)；grader 用 **gpt-4o**（GRADER_APIYI_KEY，已配通）。成对美学验证 75%(可用)；**VQA 指令验证卡住**——因评测集是"不传room_type"的非真实路径生成的，无法公平验证指令遵循。**trace 接入后用真实数据重测才有意义。**
4. **路径B（采难case）** 仍押后。

---

## 🔑 已坐实的关键发现（基于 85 条真实分，免费得出）

- 🔴 **`llm_judge` 已死**：分布 `{3分:29, 4分:45, 5分:11}`，无任何 1/2 分；且是「盲评」——只喂 style/room/prompt 文本给 DeepSeek，**从不看图**。永远不给差评 + 看不见图 = 无评测价值。
- ⚠️ **`clip_score` 近无效**：85 张挤在 `0.762~0.934`（极差 0.17），区分度极低，毛坯↔精装图-图相似度语义可能反。
- 🟢 **`structural_fidelity`（边缘 SSIM）** 落在 `56.6~77.9`，是唯一值得先验证保留的本地评分器。

---

## 🗓️ 会话日志（倒序，最新在上）

### 2026-07-01 · trace 管道第3步：后端埋点落地（代码完成 push，待用户部署）
- **两个卡点拍板**（查服务器运维记忆后收窄）：
  - (a) trace 路径 → `backend/data/traces.jsonl`，但**统一读 env `TRACE_LOG_PATH`**（服务器想换仓库外只改 .env）。已核实：部署脚本的 `git checkout -- .`/`git pull` 只动**已跟踪**文件，未跟踪的 jsonl 不会被冲掉 → 放仓库内安全。已加进 `.gitignore`。
  - (b) 部署方式 → CI(`deploy.yml`) 6/12 起禁用、纯手工，推 main 不自动上线 → **立即 commit+push**，用户择时手动 `git pull`+重启后端。
- **三处改动（只加不改，不动生图逻辑）**：
  1. 新建 `backend/app/utils/trace_logger.py`：`write_trace/new_trace_id/image_hash`，全程 try/except 吞异常（绝不拖垮生图），追加写 JSONL，字段与 `schemas.py::Trace` 对齐但**不 import evals**（解耦），白名单丢多余键、自动补 trace_id/created_at。
  2. `llm_client.analyze_room_and_generate_prompt`：两个返回点注入 `data["vision_used"]`（视觉成功=True / 静默降级盲DeepSeek=False）——原本两条路都返回 code:0 无法区分，这是量化「静默降级隐患频率」的关键。
  3. `image.py` /generate 末尾埋点：input相对路径+hash / style+room_type+custom_prompt+aspect_ratio(=真实指令) / enhanced_prompt / model_used / vision_analysis_ok / latency_ms / output相对路径 / success。**v1 只记成功生图**（失败会删 input 图、且 to_image_pair 需 output → 失败 bad case 留给第4步反馈捕获，不动失败清理逻辑）。
- **验证**：3 文件 py_compile 通过；`write_trace` 独立冒烟（写临时路径，丢多余键、补 created_at 均 OK）；端到端 `Trace.from_dict → to_image_pair` 产出 `dataset_split=production` 的 ImagePair（第5步依赖已提前验掉）。
- **第5步导入器完成**（新建 `evals/dataset/import_traces.py`，本地测通、真数据未碰）：读 traces.jsonl → 逐条 `to_image_pair` → 合并进 `real_metadata.json`（split=production）。**幂等**（按 trace_id 去重，跑两次第二次新增0）、**只导入 success=True 且图片本地存在**的 trace（缺图/失败/坏JSON行均跳过告警）、pair_id 用 `prod_NNN` 续接。用法 `python -m evals.dataset.import_traces <路径> [--images-root ..] [--no-require-images]`。
- **节奏调整**：本地 trace 代码（埋点+导入器）先**不 push**，攒着等第4步或部署时统一上。用户 pivot 到模块二。
- **第4步（用户点评埋点）降为待办**：见「下一步」第2条。

### 2026-06-30（下半场）· 视觉Judge v2实战 → 挖出产品房型缺陷(实为评测集缺陷) → pivot真实trace
- **内化外部阅读 + grader 设计转向**：深度研究(27来源/对抗式核实)→ `RESEARCH_IMAGE_EVAL.md` + `VISION_JUDGE_DESIGN.md`第7节。
  关键结论：MLLM 直接打标量分不可信，**成对(pairwise)/VQA 拆是非题才与人类一致**；VIEScore(条件合成评测)≈0.4 接近人类上限(人-人才0.45)；结构维是 VLM 最弱(继续用 structural_fidelity)；成本 ≈$0.05/次。
- **视觉Judge v2重写**(提交 447aa02)：四维标量 → `score_instruction_vqa`(指令拆是非题)+ `compare_pairwise`(美学两图比，正反消位置偏见)。
- **grader API 通道折腾**：产品 key 仅图像生成模型通道，纯理解模型 gemini-2.5-flash「无可用通道」。先用 gemini-2.5-flash-image(图像模型)顶替→当评委太宽松(同 llm_judge 病)。**用户新开专用 grader key**(`GRADER_APIYI_KEY`，gpt-4o 已配通，vision_judge 默认改 gpt-4o + 优先读此 key)。
- **首轮验证(gpt-4o)**：成对美学 **75% 通过**(扩到12对)；**VQA 指令与人工金标准仍不相关**——但根因是 criteria 错配：gpt-4o 严格揪房型不符，而人工 instruction 分当时在评风格。
- **⚠️ 一次错误 + 回滚(重要教训)**：据"房型跑偏=失败"重校准了 instruction 金标准(砍27个)。**用户第一性原理质疑**→复核发现：前端真实用户**会选 room_type 并传后端**(RoomTypeSelector+api.js)，而评测集 `batch_generate` **故意不传 room_type**(走真实用户不走的降级路径)。所以"71%房型跑偏"是**评测集生成方式的产物，非产品 bug**；重校准前提错误(生成时没给房型指令，做成客厅不算违背)→ **已回滚**(提交见 revert)，gold 恢复原状。教训：**不明确的先问、动生产代码前先核实真实路径，别下结论。**
- **顺带定位的真隐患(不影响真实用户)**：产品 `analyze_room_and_generate_prompt` 想用 Gemini 视觉识别房型，但产品 key 无该通道 → 静默降级到盲 DeepSeek(看不见图)。真实用户因为传了 room_type 不受影响，但这条静默降级路径仍是隐患(记备查)。
- **pivot：真实用户 trace = 评测集头号来源**(用户独立想到，契合 Hamel"Source from Reality"/Anthropic trace)。已做：(1)排查确认无集中式 trace(前端仅 localStorage、后端仅存未关联的图片文件)；(2)**定义 `Trace` 数据结构**写进 `schemas.py`(含 to_image_pair 转换器，用户决策：v1只记首次生图不含精修、用户量~十几无隐私顾虑)。下一步=后端埋点(见"下一步立即行动"两个卡点)。
- **保留未动**：VQA 房型门(对真实用法有效，待评测集有真实room_type再验证)；intrinsic_difficulty(上半场成果，有效)。

### 2026-06-30（上半场）· 模块一深化：看图定内在难度（取代文件名假象）+ 内化外部权威阅读
- **背景**：用户上完张和老师第2节课（构建数据集），要把「广度+难度分布」原则落到现有 85 张评测集。第一性原理澄清：我们**不训权重→没有「训练集」**，老师那两个案例(手机人像/特斯拉)是训模型业务才需训练集；我们真正要隔离的是「开发集/dev」，且现阶段先不做隔离，专注把 85 张做对。
- **审计发现假象**：旧难度从文件名关键词推 → 45 张 standard 全被默认「易」。审计 + 来源×难度交叉坐实是**文件名假象**。
- **做了（看图重标）**：5 个并行子代理逐张 Read 毛坯原图，按 4 档 rubric(易/中/难/极难)看图判定内在难度；用户复核同意写回。
  - 新增 `evals/data/intrinsic_difficulty_labels.json`(版本化看图标签) + `evals/dataset/apply_intrinsic_difficulty.py`(幂等)。
  - real_metadata + eval_results 每对加 `intrinsic_difficulty`，**不动 `difficulty`(结果难度，人工分反推)**——两轴并存。room_type 32→38(补空6/解冲突3，原值留 metadata.room_type_original)。
- **关键纠错**：standard 45 张 旧「易45/中0/难0/极难0」→ 看图「易12/中13/难16/极难4」。**33/45 实为中/难/极难**。
- **新内在难度分布**：易17/中29/难30/极难9 → 易中54% / 难35% / 极难10%，**落在方法论目标曲线内**（之前担心「太软」是假象，实为适中偏难，合格）。小缺口：极难卡 10% 下限。
- **写回后才浮现的发现**：内在难度 × 结果难度 **几乎不相关**——内在=hard 的房 70% 结果反而做得好(21/30 结果=easy)；内在=easy 的房一半以上做砸(9/17 结果=hard)。**坐实：模型失败不由房间结构难度驱动，而由美学/指令两维驱动**（我们没可信尺子那两维）→ 第 N 次指向视觉 Judge。
- **同日**：内化两个外部权威阅读链接(Anthropic《Demystifying evals》+Hamel evals 合集 8 来源)→ 新建 `READINGS.md` + METHODOLOGY 第9节(见对应提交)。视觉 Judge 上轮做了两处免费加固(美学去耦合+两极判别力+few-shot锚定+留出)。
- **下一步**：① 视觉 Judge 探价验证(花钱，待 APIYI_KEY)；② 或先用 structural_fidelity 手动跑通一次模块五闭环(用户倾向押后视觉 Judge 时可选)。模块一广度缺口(极难偏少/room_type 天花板32~38)已知，路径B 采难 case 仍押后。


### 2026-06-26 · 评测集深化路径A：激活切片能力 + 失败地图
- **目标**：评测集深化。三岔路中选「路径A（免费）」——不采新图，先把现有 85 条变得可切片，并产出失败地图。用户原则：「先做有可信尺子能衡量的」。
- **做了**：写幂等脚本 `evals/dataset/enrich.py`：① 从文件名回填 room_type(32/85，识别不出留空不硬造) + 结构难度 tags(small_space/irregular_layout/duplex/exposed_beam/cluttered/basement, 35/85)；② 从人工金标准 overall 反推 difficulty(hard≤2 / medium=3 / easy≥4，85/85)。写回 real_metadata.json(源头, runner 重跑自动带) + eval_results.json(看板当下即可切片)。
- **字段归类(第一性原理)**：room_type/tags=输入固有属性→real_metadata；difficulty=人工 overall 反推的"模型表现/结果"→单独成字段不混入输入 tags，以便做「输入属性 × 失败结果」交叉。
- **失败地图关键发现**：
  - 🔑 **structural_fidelity 在难度档间几乎不变**(hard56.5/med59.1/easy57.7)，而人工 overall 是 1.50/3.00/4.27——**不是 bug，是它"聚焦单维不越界"的体现**：模型"整体烂"的主因落在美学+指令两维，正是我们没可信尺子的地方 → 再次坐实视觉 Judge 必要性。
  - 失分重灾区房型(人工 overall 真值)：餐厅2.0/阳台2.0/卧室2.67/厨房2.80 << 客厅3.17/书房4.0。⚠️小样本(餐厅阳台n=4,卫浴书房n=2)，方向性非定论。
  - 反直觉：standard 分片最难(44%hard, overall2.84) > competitor/corner_case。
- **验证**：完整性 0 缺失 0 损坏；loader 列出 6 tags+7 room_types；看板 health=200 无报错。
- **下一步**：路径B(采集领先当前能力的难case)用户同意押后到视觉 Judge 补齐美学/指令两维之后再做。

### 2026-06-25 · 退役 iou + fid 桩评分器
- **目标**：清理 registry 里仍注册、但从未实现真值的 iou/fid（Real 桩返回 None、Mock 伪造随机分），堵死 runner 重跑注入假分/null 的隐患。用户在三条岔路中选「先免费清 iou/fid 桩」。
- **做了**：`registry.py` 移除 create_iou_scorer/create_fid_scorer 的 import 与工厂注册；扩充退役注释（含 iou/fid 原因与日期）。eval_results.json **无需改**——iou/fid 本就没有数据列（现存唯一列=structural_fidelity）。iou_scorer.py/fid_scorer.py 保留备查。
- **验证**：registry.initialize 后仅 `['structural_fidelity']`；可信度报告正常（只剩 structural_fidelity +0.418）；看板 `import evals.ui.app` 通过。
- **发现（未做，已记入「下一步」第4条）**：`sidebar.py` 仍按静态 config.METRIC_RANGES 渲染滑块，4 个退役指标（含 clip/llm_judge）残留其中 → 侧边栏有 4 个作用于空列的死滑块。根治需让 UI 数据驱动，属独立 UI 诚实性问题，待用户拍板。
- **方法论**：与退役 clip/llm_judge 同一原则——不让「能产分但分无意义/无真值」的评分器留在生产路径上；诚实的评测平台 = 注册表里每一个评分器都对得起一次重跑。

### 2026-06-21（夜）· 退役 clip + llm_judge，看板只留可信分
- **目标**：用户发现概览 CLIP/LLM 仍是旧分；结构保真度其实已是新值（57.409）。决定退役两个已判死指标而非花成本刷新。
- **做了**：registry 移除 clip_score/llm_judge 工厂与 import（torch 依赖随之解除，.py 文件保留备查）；
  eval_results.json 清除这两列共 170 个分值，加 retired_metrics 元数据。
- **验证**：registry 无 torch 干净初始化；可信度报告只剩 structural_fidelity +0.418；概览只显示结构保真度。
- **方法论**：不为"看起来完整"去花成本刷新已知无用/有害的指标——让平台与判决一致才是诚实的评测。

### 2026-06-21（傍晚）· 阶段 2 双线并行：结构评分器抢救成功 + 视觉 Judge 设计
- **目标**：免费抢救 structural_fidelity + 同步设计视觉 Judge 待命（用户选「两者并行」）。
- **做了**：
  - 装结构依赖（numpy/opencv/skimage），写消融脚本 `structural_ablation.py`，7 个候选结构度量 vs 人工结构金标准。
  - **关键发现**：现版主力分量 Canny 边缘 SSIM 几乎零相关（+0.08）——好装修新增家具边缘淹没了它；64×64 粗布局灰度 SSIM = +0.417 最佳。
  - 重写 `structural_fidelity.py` 改用 64×64 低分辨率 SSIM 单度量；重算 85 条写回 eval_results.json。
  - **结果**：structural_fidelity vs 结构 **+0.170 → +0.418**（2.5 倍，过显著线），且对美学/指令近零（聚焦干净）。
  - 写 `VISION_JUDGE_DESIGN.md`（阶段 3 蓝图：双图输入+rubric+JSON、apiyi gemini-2.5-flash、成本框架、验收 DoD）。
- **方法论沉淀**：① 度量驱动迭代——靠消融实验而非拍脑袋找病根；② **拒绝过拟合**——不追 lowres32 的 +0.434（与 lowres64 差 0.017 在 n=85 属采样噪声）；③ 好指标应「聚焦单维、不越界」。
- **下一步**：见上「下一步立即行动」。

### 2026-06-21（下午）· 阶段 1 完成：评分器全军覆没
- **目标**：标金标准 → 跑可信度 → 给评分器定生死。
- **做了**：用户在看板标满 **85/85** 金标准（四维度用满 1-5）；跑 `python -m evals.scorer.credibility`（全 85 条重叠）。
- **关键结论（n=85，显著阈值 |Spearman|≈0.21）**：
  - 🔴 **clip_score**：vs 综合 -0.26、vs 美学 -0.31 → **显著负相关 = 反指标**。印证「图-图相似度评毛坯→精装语义反」。弃用。
  - 🔴 **llm_judge**：各维度全在 ±0.21 内且偏负 → 纯噪声。盲评（看不见图）的必然。判死，需视觉模型重做。
  - 🟡 **structural_fidelity**：vs 结构 +0.17 → 唯一正向但未达显著。方向对、实现糙，阶段 2 抢救对象。
- **方法论沉淀**：「能打分 ≠ 分可信」被自有数据证伪三例；可信度必须先量化才能谈优化——这是 L2 命门的实证。
- **下一步**：见上「下一步立即行动」（阶段 2）。

### 2026-06-21（上午）· 阶段 0 启动 + 文档地基
- **目标**：通盘梳理评测体系现状与鸿沟 → 定计划 → 启动阶段 0+1。
- **做了**：
  - 全面摸查 evals/（方法论、评分器、执行器、可信度地基、UI、数据规模），产出通盘梳理 + 鸿沟分析 + 成熟度阶梯。
  - 验证启动链路干净（看板不会触发 torch/cv2 重依赖，可安全用轻量三件套起步）。
  - 建 `evals/.venv`，安装 streamlit/pandas/Pillow（🟡 进行中）。
  - 新建 `requirements-lite.txt`、`ROADMAP.md`、`PROGRESS.md`（本文件）。
- **结论**：不缺代码，缺的是「让系统第一次通电」+「证明评分器可信」（L2 命门，离启动只差装依赖+标 20 条）。
- **卡点/下一步**：见上「下一步立即行动」。
