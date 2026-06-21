# 视觉 Judge 设计方案（阶段 3 待命蓝图）

> 状态：**设计完成，待用户决定花钱后实施**。配套：`METHODOLOGY.md` 第 3/4 节、`ROADMAP.md` 阶段 3。
> 本文件回答「视觉 Judge 长什么样、怎么调、花多少钱、怎么验收」，让阶段 3 一声令下即可开工。

---

## 1. 为什么必须有它（动机锁死）

阶段 1 已用 85 条金标准证明：**当前自动评测没有任何可信信号**。
- `clip_score`：与人类审美显著负相关（反指标）。
- `llm_judge`：盲评，纯噪声。
- `structural_fidelity`：只可能覆盖「结构」一维，且需抢救。

而评测的另外两维——**美学质量、指令遵循——是语义问题，按方法论铁律只能由「真正看见图」的视觉模型判**。
本地算法永远做不了。故视觉 Judge 是补齐可信自动评测的唯一路径。

---

## 2. 设计原则（全部从 METHODOLOGY 推导）

1. **真正看见图**：输入 = 毛坯原图 + AI 效果图**两张图**，而非只喂文本（这正是旧 llm_judge 的死因）。
2. **结构化 rubric**：1-5 分，分维度打（aesthetic / instruction / structural 交叉验证 + overall），逼模型给出**可解释理由**。
3. **防锚定**：Judge 不喂任何已有自动分；与人工金标准的对齐用**留出验证**，不让模型见金标准。
4. **统计纠偏（稳定性）**：同图多次/多模型投票，量化方差（CV），用中位数/均值降噪；记录每次原始分。
5. **上线前先证明可信**：用现成 85 条金标准算 Spearman/Pearson/归一MAE，**显著优于现状才允许采用**（红线）。

---

## 3. 技术方案

### 3.1 通道与模型（复用项目现有 API易 通道）
- Endpoint：`https://api.apiyi.com/v1beta/models/{model}:generateContent`（Gemini 原生格式，与后端一致）。
- 密钥：`APIYI_KEY`（回退 `LLM_APIYI_KEY`），与 `getgoapi_client.py` 同源。
- 模型候选（**理解模型，非图像生成模型**，上线前需先探测 key 是否开通）：
  - 主力：`gemini-2.5-flash`（快、便宜，跑全量 + 多次投票）。
  - 仲裁/疑难：`gemini-2.5-pro`（贵、强，用于分歧样本或最终校准）。
  - ⚠️ 现有 `gemini-3-pro-image-preview` / `gemini-2.5-flash-image` 是**图像生成**模型，不能用来评图。

### 3.2 请求体（双图 + rubric → JSON）
```jsonc
{
  "contents": [{ "parts": [
    { "text": "<rubric 提示词：见 3.3>" },
    { "text": "【图1：毛坯原图】" },
    { "inlineData": { "mimeType": "image/jpeg", "data": "<base64 毛坯>" } },
    { "text": "【图2：AI 效果图】" },
    { "inlineData": { "mimeType": "image/png", "data": "<base64 效果图>" } }
  ]}],
  "generationConfig": { "responseModalities": ["TEXT"], "temperature": 0.2 }
}
```
- 解析 `candidates[0].content.parts[].text` → 抽 JSON（带正则兜底，复用 llm_judge 的 `_parse_score` 思路扩成多维）。
- 失败重试 + 退避（参考 getgoapi_client 的 MAX_RETRIES 模式）；异常 fallback 记为 None（不污染均值）。

### 3.3 Rubric 提示词（草案，三维度 1-5 + 理由）
```
你是资深室内设计评审。下面【图1】是装修前的毛坯原图，【图2】是 AI 基于它生成的效果图。
目标风格：{style}；房间类型：{room_type}；用户需求：{prompt}。
请严格独立评分（1-5 分，可给低分），输出 JSON：
{
  "structural": <1-5>,   // 毛坯的墙体/门窗/承重/户型结构是否被如实保留，未被乱改
  "aesthetic":  <1-5>,   // 设计感/配色/材质/光影/整体美观
  "instruction":<1-5>,   // 是否符合目标风格/房型/需求
  "overall":    <1-5>,   // 综合主观评价
  "reason": "<两句话理由，先说硬伤>"
}
只输出 JSON。烂图必须敢给 1-2 分。
```

### 3.4 代码落点
- 新增 `evals/scorer/vision_judge.py`：`RealVisionJudgeScorer`（多维返回）+ `MockVisionJudgeScorer`。
- 注册进 `registry.py`；`runner.py` 重跑写入 `eval_results.json`（多维分需扩 schema，或拆成 `vision_structural` / `vision_aesthetic` / `vision_instruction` 多个 metric 进 `METRIC_RANGES`）。
- 投票/方差走 `credibility.measure_reliability()`（已支持 repeats）。

---

## 4. 成本估算（框架，单价待实测确认）

单次评测 = 2 张图输入（毛坯+效果，约几十万~百万级 token 视分辨率）+ 短 JSON 输出（~150 token）。
- **全量一轮** = 85 条 × 1 次。
- **投票纠偏** = 85 条 × 3 次（推荐，用于算方差）。
- **疑难仲裁** = 仅分歧样本 × pro 模型（少量）。

> ⚠️ 未写死单价（避免拍脑袋）。Gemini-2.5-flash 视觉理解单价很低，**85×3 次的量级预期在「几元人民币」内**，属于可一次性验证的小钱。实施第一步 = 先用 1-2 条探测单价与延迟，再决定投票次数。
> 控本手段：图先缩到 512~768px 再 base64（结构/美学判断不需要原分辨率），可大幅降 token。

---

## 5. 验收标准（DoD，过了才算可用）

1. vs 人工金标准（85 条）：主维度 Spearman **显著为正且 > 0.21**，且**明显优于** structural_fidelity 的现状。
2. 稳定性：3 次投票的变异系数 CV 可控（量化记录，不要求 0，但要知道波动多大）。
3. 美学 / 指令遵循两维：至少有一维达到「弱-中」正相关（这是本地算法做不到、视觉 Judge 必须补上的价值）。

---

## 6. 红线

- **未通过第 5 节验收前，视觉 Judge 的分不得用于任何「自动优化/改代码」决策**——否则又是放大噪声。
- 先探单价 → 小批验证对齐度 → 达标再跑全量、再谈进入 L4/L5。
