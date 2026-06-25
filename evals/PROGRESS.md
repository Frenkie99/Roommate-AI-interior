# 评测体系 进度 / 复盘日志

> 配套：`ROADMAP.md`（分阶段计划）· `METHODOLOGY.md`（哲学）· `DATASET.md`（数据自检）。
> **重启会话第一眼看本文件顶部「当前状态快照 + 下一步立即行动」即可续接。**
> 维护规则：每次会话结束前更新顶部快照，并在「会话日志」**最上方**新增一条（倒序）。

---

## 📍 当前状态快照

- **成熟度位置**：L1→L2 推进中。**已有第一个被数据证明可信的评分器**（structural_fidelity +0.418）。
- **当前阶段**：阶段 0 ✅ · 阶段 1 ✅ · 阶段 2 🟡（结构评分器抢救成功；clip+llm_judge+iou+fid 四个无效/桩评分器已全部退役；视觉 Judge 已设计待实施）。
- **看板现状**：概览/可信度只显示唯一可信指标 structural_fidelity（+0.418）。registry 现仅注册 structural_fidelity。clip/llm_judge 的数据列已从 eval_results 移除；iou/fid 本就无数据列。
- **环境**：本地 Mac（Apple Silicon arm64，系统 Python 3.9.6）。
  - venv：`evals/.venv`（已建）。
  - 轻量三件套：✅ streamlit 1.50.0 / pandas 2.3.3 / Pillow 11.3.0。
  - 结构评分依赖：✅ numpy 2.0.2 / opencv 4.13.0 / scikit-image 0.24.0。
  - torch/transformers：未装（仅 clip 需要，而 clip 已判弃用 → 预计不再装）。
- **看板**：✅ 可启动。命令见下方。冒烟测试通过（UI 全导入、85 对图加载、85/85 图片路径可显示）。
- **数据**：85 对真实评测图齐全；`eval_results.json` 含 85 条真实分（clip/structural_fidelity/llm_judge）。
- **金标准**：`gold_labels.json` 已存在，**85/85 全标完**（标注人 frenkie），四维度均用满 1-5、方差充足，是有效的真值尺。

## ⏭️ 下一步立即行动

1. **实施视觉 Judge（阶段 3，需花钱）**：方案见 `VISION_JUDGE_DESIGN.md`。第一步=探单价+1-2 条小验，达标再跑全量。补齐美学/指令两维——目前这两维无任何可信信号。
2. **（可选）评测集深化（阶段 4/鸿沟④）**：85 条按难度分层、补「领先当前能力」的难 case。
3. ~~**（可选）iou/fid 处置**~~ ✅ **已完成（2026-06-25）**：iou/fid 已从 registry 退役（同 clip/llm_judge），runner 重跑不再注入假分/null。.py 文件保留备查。
4. **（遗留 UI 隐患，未做）侧边栏死滑块**：`sidebar.py` 按 `config.METRIC_RANGES` 给每个指标渲染滑块，但 4 个已退役指标（iou/fid/clip/llm_judge）仍在 METRIC_RANGES 里 → 侧边栏显示 5 个滑块，4 个作用在不存在的数据列上（无效）。根治法=让 UI 按「数据实际存在的列」渲染，而非静态 config。属独立的 UI 诚实性问题，待用户决定是否做。

---

## 🔑 已坐实的关键发现（基于 85 条真实分，免费得出）

- 🔴 **`llm_judge` 已死**：分布 `{3分:29, 4分:45, 5分:11}`，无任何 1/2 分；且是「盲评」——只喂 style/room/prompt 文本给 DeepSeek，**从不看图**。永远不给差评 + 看不见图 = 无评测价值。
- ⚠️ **`clip_score` 近无效**：85 张挤在 `0.762~0.934`（极差 0.17），区分度极低，毛坯↔精装图-图相似度语义可能反。
- 🟢 **`structural_fidelity`（边缘 SSIM）** 落在 `56.6~77.9`，是唯一值得先验证保留的本地评分器。

---

## 🗓️ 会话日志（倒序，最新在上）

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
