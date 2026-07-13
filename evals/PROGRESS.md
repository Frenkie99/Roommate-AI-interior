# 评测体系 进度 / 复盘日志

> 配套：`ROADMAP.md`（分阶段计划）· `METHODOLOGY.md`（哲学）· `DATASET.md`（数据自检）· `PRODUCT_CONTRACT.md`（产品契约：忠实还原vs效果优化，含裁决规则+产品待办）。
> **重启会话第一眼看本文件顶部「当前状态快照 + 下一步立即行动」即可续接。**
> 维护规则：每次会话结束前更新顶部快照，并在「会话日志」**最上方**新增一条（倒序）。

---

## 📍 当前状态快照

- **成熟度位置**：L1→L2 推进中。**已有第一个被数据证明可信的评分器**（structural_fidelity +0.418）。
- **课程进度（用户上网课，按模块推进）**：模块一(数据集) ✅ · 模块二(eval harness) ✅ 收官(除部署采集开关) · **模块三(Grader) 🟢 主体收官（2026-07-09）：基建四刀落地 + 85/85 二元真值收齐 + 🎉 美学成对 judge 验收通过（第二把可信尺子，test 78.6%≥75% 门槛、34 对 0 判反、已记台账）。剩指令维 VQA 的 test 定版（押后待 trace 真实数据——当前评测集验不公平）**。
- **两把可信尺子**：① structural_fidelity（结构维，标量，Spearman +0.418）② vision_judge 成对美学（美学维，A/B 比较器，一致率 78.6%/0判反）——**使用域=成对比较（模块五新旧 A/B），不产标量分不进 registry**，见 `VISION_JUDGE_DESIGN.md` 第5节验收状态表。指令维仍无尺（等 trace）。
- **模块三基建（2026-07-09 四刀，全本地测通）**：
  1. **分类校准地基**：金标准二元化（overall≥4 pass/≤2 fail 派生 + `binary_verdict` 显式裁决 + `critique` 判词字段）；`credibility.py` 新增混淆矩阵+TPR/TNR+Wilson 95% 区间（课程"把 Judge 当分类器验证"）；标注页加二元裁决/critique/待仲裁队列；可信度面板加「分类校准」区。
  2. **Judge 数据划分**：85 条 → few-shot 池 6（3pass+3fail，跨分档）/ dev 53 / test 26，分层（二元类别×有无房型）确定性抽样，`data/judge_split.json` 落盘 + **test 消费台账**（一版一次纪律）。structural_fidelity 已定型不受约束、继续全集报相关性。
  3. **vision_judge v2.1**：prompt 对齐课程模板——reason 前置于 verdict（先分析后结论）、每题写清 pass/fail 判据、verdict 加 na 退出机制（不计分母）、few-shot 池人工判词嵌入（critique 优先，池外永不入 prompt 防泄漏）。
  4. **AI 分析模块**（课程"Agent 裁判/开天眼"落地）：Badcase 面板每 case 一键「🤖 AI 分析」→ 后台 `claude -p`（只读工具白名单 Read/Glob/Grep）按五问固化框架归因 → 结构化 JSON 沉淀 `data/ai_analysis/` → 聚合成失败模式分布（半自动开放编码）。prompt 内置**已知评测集缺陷备忘**防"重新发现假 bug"。
- **模块二成果（2026-07-02 四刀，全部本地测通、未 push、ahead 5）**：
  1. CLI Runner：按 split/房型/难度/tags 筛子集跑、失败隔离、--resume 续跑、合并写盘非破坏（保富化维度）、last_run 快照、--dry-run/--report-only；
  2. 看板「用户使用过程」tab：trace 5 步时间线回放（示例数据预览，真实 traces.jsonl 一进自动切换）；
  3. trace 白盒化：补记 vision_analysis(AI对房间的理解)/prompt_source(提示词走哪条路)/latency_breakdown(分阶段耗时)，房型跑偏红字告警；
  4. 科学护栏（Fable 5 审计后修缮）：小样本⚠️、组间差vs全体std噪声判定、读数须知、反静默丢case告警、看板「分维度报告」tab。
- **审计钉在墙上的三件事**：(a) 评测集 85 条全是非真实路径生成，指令维度不能代表产品（解药=trace 部署）；(b) structural_fidelity 各切片差异全在噪声内 = **现有唯一尺子的信息已挤干，瓶颈在尺子数量**（美学/指令两维无可信尺）；(c) difficulty 是结果反推，勿倒果为因。
- **当前阶段**：阶段 0 ✅ · 阶段 1 ✅ · 阶段 2 🟡（结构评分器抢救成功；clip+llm_judge+iou+fid 四个无效/桩评分器已全部退役；视觉 Judge 已设计待实施）· 阶段 3(评测集) 🟡（路径A完成：85 条已可切片+失败地图；路径B采新难case押后）。
- **看板现状**：8 个 tab（新增「用户使用过程」「分维度报告」）。概览/可信度只显示唯一可信指标 structural_fidelity（+0.418）。registry 现仅注册 structural_fidelity。clip/llm_judge 的数据列已从 eval_results 移除；iou/fid 本就无数据列。
- **评测集**：85 条已激活切片。**两个难度轴并存**：`intrinsic_difficulty`(内在难度，2026-06-30 看图判定 易17/中29/难30/极难9，脚本 `apply_intrinsic_difficulty.py`+标签 `intrinsic_difficulty_labels.json`) 与 `difficulty`(结果难度，从人工 overall 反推)。room_type 38/85(看图补到)+结构 tags 35/85。早期回填脚本 `enrich.py`(幂等)。失败地图见会话日志 2026-06-26。
- **环境**：本地 Mac（Apple Silicon arm64，系统 Python 3.9.6）。
  - venv：`evals/.venv`（已建）。
  - 轻量三件套：✅ streamlit 1.50.0 / pandas 2.3.3 / Pillow 11.3.0。
  - 结构评分依赖：✅ numpy 2.0.2 / opencv 4.13.0 / scikit-image 0.24.0。
  - torch/transformers：未装（仅 clip 需要，而 clip 已判弃用 → 预计不再装）。
- **看板**：✅ 可启动。命令见下方。冒烟测试通过（UI 全导入、85 对图加载、85/85 图片路径可显示）。
- **数据**：85 对真实评测图齐全；`eval_results.json` 含 85 条真实分（clip/structural_fidelity/llm_judge）。
- **金标准**：`gold_labels.json` 已存在，**85/85 全标完**（标注人 frenkie），四维度均用满 1-5、方差充足，是有效的真值尺。

## ⏭️ 下一步立即行动（2026-07-13 部署完成更新）

> **✅ 部署上线完成（2026-07-13）**：服务器 git pull（9504fcc→565c424 fast-forward 零冲突）+ 重启 roommate-backend，
> 启动干净、内存健康（可用 459Mi/swap 0）。生产冒烟通过 ×2（curl 直打 + 用户真实操作）：**P0 画幅修复生产坐实**
> （竖图 1334×2000 输入 → 896×1200 竖构图输出，修复前会强转 4:3 横图）。trace 采集已通电（待确认落盘条数）。
> **重生成实验已取消（2026-07-13 用户拍板）**：P0 修复已在生产双冒烟坐实（竖入竖出），无需再花钱对照重生成。
> 模块五闭环的"量化裁决"改由**真实 trace 自然合拢**：修复后的真实用户竖图结果攒起来，与修复前评测集里的 8 条 auto bug case 对比即可（零成本、且是真实分布）。
> **🎯 当前落点**：让 trace 自然积累（已 2 条），定期拉回本地看板观察；下一个动手项 = 第 4 步用户点评埋点（bad case 金矿）。
> **✅ 前端静默失败已修并上线（同日 150147c）**：超 10MB 上传前拦截+toast 常驻+上传框标注限制；服务器构建时发现 dist 为 root 属主（EACCES）已 chown 给 admin——**同时坐实了 CI 上传步骤失败的根因，恢复自动部署的路障已清**。另：服务器 .env 无 APIYI_KEY，生图走 LLM_APIYI_KEY 兜底（实测可用，暂不动）。
>
> **五模块复盘定格（2026-07-10）**：一~70%(来源缺陷=唯一结构性短板) · 二~95%(差部署开关) · 三~85%(两把可信尺子,指令维等真实数据) · 四~80%(AI归因+失败分布,差feedback) · 五~30%(第一闭环走完80%,差部署+重生成验证)。
> **数据定位已定调**：85 条批量数据部署后转「回归评测集」（防退化），真实 trace = 「能力评测集」（产品行不行）。production 图片是真实用户房间照片，**不入 git**。

1. ~~【用户人工任务】二元仲裁 + few-shot critique~~ ✅ **2026-07-09 完成**：85/85 二元真值齐（pass 49/fail 36，人工显式裁决 13 条），few-shot 池 6 条 critique 全部写好且按「呈现vs内容」契约线编码（见 `PRODUCT_CONTRACT.md`）。仲裁过程逼出产品契约问题（视角矫正/扩图/拓扑造假三档失真），四点判断+裁决规则+产品待办 P1-P5 已沉淀该文档。
2. ~~【刀4】vision_judge 验收~~ ✅ **美学侧 2026-07-09 完成**（dev 95% → test 78.6% 过门槛，台账已记，总花费 ≈11万 token ≈ 3-4 元）。**指令 VQA 的 test 定版押后待 trace 真实数据**（门槛不变：TPR/TNR ≥85% 且 Wilson 下界 ≥70%）。pair_018 已从校准剔除（评测集缺陷：房型随机分配错误；机制已通用化——标注页有「从校准剔除」开关）。
3. **【待用户拍板】部署 trace 采集**：push 已全部完成，只差服务器 `git pull` + 重启 `roommate-backend.service`。解锁真实评测集 + 视觉 Judge 公平验证 + AI 分析模块的完整 trace 上下文。
4. **【待办·独立】第4步用户点评埋点**（动前端）：效果图下加「满意/重新生成/下载/不要了」按钮写 feedback + 前端生成 session_id 回传。bad case 金矿。
5. **【远期】生成式重跑 + pass^k**（花钱）：面向用户的产品 pass^k 是体感指标（课程）；等部署+评分器补齐后，挑 10-20 代表 case 各生成 3 次算 pass^3。
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

### 2026-07-13 · 部署上线收官：P0 修复+trace 采集进生产，冒烟双确认
- **部署路径**：用户手动网页终端执行（SSH 密钥方案因密码不对未走通）。git pull fast-forward 9504fcc→565c424 零冲突；
  重启后 `Application startup complete`，无新增依赖、内存健康（可用 459Mi，swap 0）。
- **冒烟双确认**：① Claude 从本地 curl 直打 `POST /api/v1/generate`（竖图 1334×2000 + modern_luxury/living_room）→
  成功，输出 896×1200 **竖构图** = P0 修复生产坐实；② 用户网页端真实生成成功，同样竖向输出。
- **排查插曲（有价值的产品发现）**：用户首次网页生成"没反应"——实为**图片超 10MB 被后端拒绝**，而 PlaygroundPage
  把错误写进 statusText、进度条随 isGenerating=false 秒消失 → 失败原因用户不可见。
- **当天修复上线（150147c）**：选文件即校验大小（超限 toast 报具体 MB 数）+ 生成失败 toast 常驻 6s + 上传框文案标注 10MB 限制
  + 非图片文件拖入也给提示。服务器 npm build 首跑 EACCES（dist 为 root 属主，CI 上传失败同根因）→ chown admin 后构建成功（11s 无 OOM），
  线上验证新 bundle 已生效。**副产物：恢复 CI 自动部署的权限路障已清除，后续只需重新启用 workflow 并验证。**
- **服务器环境注记**：.env 无 APIYI_KEY，生图走 LLM_APIYI_KEY 兜底（实测有图像模型权限，可用）；SEGmind key 仍缺（分割功能未通，旧账）。
- **Seedream 5.0 调研归档（同日，深度研究 102 agent/611 检索）**：纯指令编辑（无 mask 参数），Pro 支持画框视觉提示；
  保结构=SeedEdit 3.0 式奖励模型软约束，**非 mask 硬冻结**；对本项目定位=整图生成主链路的候选底模（生图模型占 20/34 失败归因），
  非 SAM 替代品。待办：部署稳定后花约 19 元（85×0.22）在回归集上跑 Lite 版，structural_fidelity+成对 judge 裁它 vs Gemini。

### 2026-07-09（下半场）· 刀4 执行：美学成对 judge 验收通过 = 第二把可信尺子诞生
- **前置**：用户完成 7 条模糊仲裁 + few-shot 池 critique（判词恰好把「呈现vs内容」契约线编码进 few-shot：016 矫正ok vs 058 盲目扩图）；仲裁中还显式改判数条（019 overall=4 但未遵循结构→fail），二元真值 85/85 收齐（pass 49/fail 36，剔除后 84 条参与校准）。
- **pair_018 校准剔除 + 机制通用化**：其 fail 判的是评测集缺陷（房型随机分配错误，源图明显是卫生间）非产品输出——混层会冤枉 judge（看图判 pass 被记 FP）。gold_store 加 `calibration_excluded`/`exclusion_reason` 字段（upsert None保留/True设置/False恢复），三处生效：二元盘点、classification_analysis、few-shot 池渲染（判词描述题目缺陷不配当示例）；标注页加剔除开关+原因框，面板显示剔除清单。
- **compare_pairwise 支持纯美学对比**：input_path=None 不发毛坯参考图（跨 case 对比时展示某一方毛坯既误导又费 token），prompt 注明"可能来自不同房间，忽略户型差异"。
- **验收协议**（`scorer/pairwise_validation.py`）：低分组(aes≤2)×高分组(aes≥4)构造清晰差距对（Δ≥2），每 case 至多出现2次、A/B位置交替消系统偏差+正反双序消位置偏见；一致率=选对/总数（tie 计不一致）+Wilson 区间；test 必须 --record-ledger --judge-version（无台账拒跑）。结果追加式落盘 `data/pairwise_validation.json`。
- **结果**：dev 20 对 **95%**（19✓/0✗/1平）零迭代过线 → test 14 对 **78.6%**（11✓/0✗/3平）≥75% 门槛，📒 台账已记（vision_judge.pairwise_aesthetic v2.1）。**合并 34 对 0 次判反**——所有失分都是保守 tie，judge 从不把丑的判成美的。总花费 ≈11.2万 in + 2.2k out token ≈ 3-4 元（预算 20 元，用了不到 1/5）。
- **使用域钉死**（验收范围即使用范围）：仅成对比较（模块五新旧 A/B / badcase 相对排序）；只验证过清晰差距（Δ≥2），Δ=1 模糊区未验证；不产标量分、不进 registry。见 VISION_JUDGE_DESIGN.md 第5节验收状态表。
- **批量归因收官（2026-07-10 凌晨，34/34 全成功，零失败）**：失败模式分布=**生图模型 20 / Prompt构建 9 / 评测集缺陷 4 / 复核非失败 1 / 评分器误判 1**（置信度 high 18/medium 17），全部沉淀 `data/ai_analysis/`，看板 Badcase 页可看聚合。
- **🎯 批量归因头号战果（已核实源码，非假设）**：9 条 Prompt构建 中 8 条独立收敛到同一根因——`backend/app/routes/image.py:131` **auto 画幅硬编码 "4:3"**，竖图（手机拍毛坯的常态）被强转横图 → 模型被迫横向虚构空间 = **"盲目扩图"的机械成因**（用户仲裁时亲手标"盲目扩图"的 pair_006/058 都在这批里）。修法一行：auto 复用 `inpaint_service.py:17 _aspect_ratio_for_size()`。已写入 PRODUCT_CONTRACT **P0（最高优先）**，P1 结构锁定实验改为依赖 P0（先消机械诱因再治模型行为）。**模块五（迭代优化）从此有了第一个具体靶子。**
- **待用户复核的归因假设**：①评测集缺陷 4 条（pair_013/069/073/083，剔除候选）；②金标准疑似误标 3 条（pair_013/030/048——agent 认为图面质量与美学 1 分矛盾，标注人复核后要么改标要么驳回假设）。

### 2026-07-10 · 收尾：五模块整体复盘 + 定格「一切汇于部署」
- 网课全部模块看完。复盘判决：**评测集骨架完整、血液不对**（结构上分片/金标准/双难度/划分/剔除一件不少；来源上 85 条全是非真实路径生成+房型缺47/85+单次采样）。解药=线上联动，而**管道已全线建成逐节测通**（埋点→scp→import_traces→Runner→看板→AI归因），唯一开关=部署。
- 部署后行动序列已排定（见顶部）：竖图对照重生成合拢闭环 → 攒1-2周trace → 指令VQA公平重验+test定版（第三把尺子）→ feedback埋点 → pass^k远期。
- 三个防乐观提醒记录在案：①真实流量小（十几用户），production split 以月计成长，85条批量数据转回归评测集不退役；②真实用户房间照片不入git；③服务器900MB内存OOM前科，部署后生图冒烟再收工。

### 2026-07-10 · P0 修复：auto 画幅自适应（用户拍板"开始修吧"）
- **改动（backend/app/routes/image.py，范围最小化）**：auto 分支改为 `Image.open(processed_image)` 取实际尺寸 → 复用 `inpaint_service._aspect_ratio_for_size()` 就近映射（1:1/4:3/3:4/16:9/9:16）；读图失败回退旧行为 4:3；显式比例路径原样不动；trace 新增 `metadata.aspect_ratio_mapped` 留痕（白名单/schema 都有 metadata 字段，零 schema 改动）。
- **验证（不花钱）**：本地无 FastAPI 环境 → scratchpad 建最小 venv（fastapi/httpx0.27/PIL/numpy 对齐 requirements），mock 生图客户端后用 TestClient 打**真实 /generate 路由**：竖图768x1024→3:4 ✓ 长竖1080x2340→9:16 ✓ 横图→4:3 ✓ 方图→1:1 ✓ 显式16:9透传 ✓ trace留痕 ✓（6/6）。测试产生的 10 个假图已清理，测试 trace 写临时文件未污染真实数据。
- **生效条件**：**服务器部署（git pull + 重启 roommate-backend.service）——与 trace 采集埋点是同一次部署，一次上线解锁两件事**。部署后跑竖图子集对照重生成，验证"盲目扩图"是否消退（这同时是 P1 结构锁定实验的前置）。

### 2026-07-09 · 模块三(Grader)基建四刀：分类校准 + Judge数据划分 + prompt模板化 + AI分析模块
- **背景**：用户看完 grader 网课（张和老师），先对齐框架→映射现状：骨架已同向（binary化/成对美学/金标准校准/评结果不评路径），真正缺「把 Judge 当分类器验证」的基建——TPR/TNR、数据划分、prompt 模板。按拍板顺序动四刀（刀4 花钱押后待确认）。
- **刀1 分类校准**：`gold_store.py` 加 `derive_binary`(overall≥4 pass/≤2 fail/=3 模糊)+`effective_binary`(显式裁决优先)+upsert 支持 `binary_verdict`/`critique`(None保留旧值/derived清除/空串清空)；`credibility.py` 加 `wilson_interval`/`classification_metrics`/`classification_analysis`(含FP/FN误判明细+split过滤)+CLI `--classify`；标注页加二元裁决radio/critique/待仲裁队列；可信度面板加分类校准区(混淆矩阵+TPR/TNR+CI+误判下钻)。**派生结果：pass 48/fail 30/模糊 7（待用户仲裁）**。
- **刀2 划分**：`dataset/judge_split.py`——few-shot 6(3pass+3fail 跨分档优先有判词) / dev 53 / test 26，(二元×有无房型)分层+seed 确定性；`data/judge_split.json` 落盘含 **test_ledger 消费台账**；重划需 --force（防 test 纯度作废）。structural_fidelity 已定型不受约束。
- **刀3 vision_judge v2.1**：reason 前置 verdict（自回归先分析后结论，课程 {"reasoning","answer"} 顺序）；每题判据写死（房型按家具功能识别/风格四要素/需求提取可核验要点）；verdict 加 na 退出且不计分母（`_norm_verdict` 精确匹配——na 和 no 都以 n 开头，老前缀匹配会把 na 误吞成 no）；few-shot 池判词嵌入（critique 优先，notes 仅"短且非疑问句"兜底——实测 notes 混数据集管理碎碎念）。
- **刀5 AI分析模块**（老师亮点落地）：`analysis/ai_analyst.py`——预配置上下文（case档案+图路径+自动分+金标准+trace白盒字段）+五问固化框架（哪环先错/证据/波及/修法/置信度）+**已知缺陷备忘**（防 agent 把"房型跑偏=非真实路径缺陷"当新 bug 重复发现，2026-06-30 教训制度化）；引擎=`claude -p` headless（=Agent SDK preset claude_code，零新依赖），工具白名单只读 Read/Glob/Grep，15min/30回合双上限；产出=结构化JSON（root_cause_stage 8枚举+证据+修复建议）沉淀 `data/ai_analysis/`；UI：Badcase 面板每 case 三态按钮（缓存/进行中/触发）+**归因分布聚合**（=半自动开放编码，直接喂模块五）。
- **验证**：统计函数单测（wilson已知值/混淆矩阵/派生边界）✅；gold_store 新字段读写回归 ✅；分类校准 CLI 端到端（structural_fidelity@55：TPR 67%/TNR 40%——再次印证 overall 由美学/指令驱动，结构尺管不了综合好坏）✅；vision_judge prompt 干跑渲染 ✅；AI 分析 pair_000 真实端到端 ✅；看板冒烟 HTTP 200 ✅。
- **认知沉淀**：①课程 90% TPR/TNR 门槛不无差别照搬——指令维（可核验客观题）照办，美学维用成对一致率≥75%（人-人上限~0.45）；②test 26 条 Wilson 区间宽±15pp，结论只用于过/不过门槛，禁止版本间精细排序；③AI分析产出定位=归因假设待人工确认，非结论。
- **审计方式**：不凭印象，跑代码坐实每个判断。三个裂缝全部实测确认：
  - [1] `select_pairs` 按难度筛会**静默丢弃**无 metadata 的新 case（如将来的 production 数据）——实测 prod_999 无告警消失；
  - [2] 报告 6 个 n<5 小样本组（study n=1！）与大样本并排排名，无任何标记；
  - [3] split 组间最大差 3.56 < 全体 std 4.88——**全部维度的组间差异都在噪声量级内**，报告却排成排行榜无一字提示。
- **审计判决（记录在案）**：模块一地基真实（金标准+看图难度是最值钱资产），但 (a) 评测集"非真实路径生成"的有效性缺陷仍在（解药=trace 部署）；(b) difficulty 结果难度有倒果为因陷阱；(c) room_type 47/85 空。模块二骨架合格，但**报告层作为"下结论的界面"不设护栏 = 最大科学性缺陷**。
- **修缮（4 处，全免费）**：
  1. `aggregator.py`：组块加 `small_sample`(n<5) 标记；markdown 头部"读数须知"三条护栏；小样本组名带 ⚠️；每表附「组间差(非小样本组) vs 全体 std」自动噪声判定；difficulty/intrinsic_difficulty 维度注解（防倒果为因）。
  2. `runner.py::select_pairs`：反静默——缺难度标注被排除的 case 显式告警+列名。
  3. 看板第 8 个 tab「分维度报告」(`ui/components/report_panel.py`)：读 eval_report.json，选指标/维度出表，小样本 ⚠️、噪声判定色条（黄=噪声内/绿=可能真信号）、一键重新聚合按钮、run 快照 caption。
  4. 顺手：新写两组件的 `use_container_width`（已弃用）→ `width="stretch"`（旧组件不动，范围最小化）。
- **验证**：全编译过；复测审计1→告警正常打出；重生成报告→护栏/⚠️/噪声判定/注解全出（所有维度判定"噪声量级内"——与已知结论一致：structural_fidelity 聚焦单维不随切片起伏）；UI 导入 OK；看板重启 8 个 tab。**未 push**（攒着，ahead 5）。

### 2026-07-02（第三刀）· 记全中间步骤：trace 从「半白盒」→ 真白盒（本地，不部署）
- **背景**：用户认可呈现端后拍板「继续记全中间步骤」。核管道(image.py /generate + llm_client)发现：`llm_analysis.get("analysis")`(AI对房间的原始理解)**返回给前端了但trace没记**，是最该补的白盒产物。
- **补记3样中间步骤(全程只加不改生图逻辑)**：
  1. `vision_analysis` = AI对房间的原始理解(识别房型/布局/采光)；
  2. `prompt_source` = enhanced_prompt走了哪条路(llm_vision/blind_deepseek/static_on_error/static)；
  3. `latency_breakdown` = 分阶段耗时{vision_ms, generate_ms}(哪步慢一眼见)。
- **改动4处**：
  - `evals/dataset/schemas.py::Trace` 加3字段(向后兼容)，`to_image_pair` metadata带上 prompt_source+vision_analysis。
  - `backend/app/routes/image.py` 分阶段计时(视觉/生图) + 按分支定 prompt_source + 捕获 vision_analysis，写进 write_trace(**只加新代码**)。
  - `backend/app/utils/trace_logger.py` 白名单加3新键(否则被丢弃)。
  - `ui/components/trace_viewer.py` ③中间过程改版：提示词来源标签+分阶段耗时+`st.json`展开AI理解+**房型跑偏红字告警**(AI识别房型≠用户选→点名根因)。
  - 示例 `sample_traces.jsonl` 补齐新字段：demo_b1 演示「用户选bedroom→盲降级→AI猜living_room→生成客厅→弃用」，中间步骤记全后一眼定位根因。
- **验证**：后端3+evals2文件 py_compile过；后端白名单写→读回3新键放行、junk键丢弃；示例贯通(source/vision_ok/detected_room_type/耗时拆解全出)；to_image_pair带新metadata；跑偏检测 demo_b1 selected≠detected=True；UI导入OK+看板重启。**未push**。
- **要素④仍差最后一步**：埋点部署上线才有真实数据(要动生产+等用户)。至此「记录」维度已白盒，「采集」开关待开。

### 2026-07-02（下半场）· 模块二第二刀：「用户使用过程」呈现端（本地，不部署）
- **背景**：用户追问「用户使用过程能否在模块二完整呈现」。诚实答：现做不到=正是要素④(Trace)，采集没部署(0真实数据)+看板无呈现界面。用户拍板：**本地先搭「呈现」不部署**(不碰生产、不破坏「攒着」)。
- **做了**：
  1. 新建看板第7个 tab「用户使用过程」(`ui/components/trace_viewer.py`)：按会话分组→选一个用户→把每次使用还原成**5步时间线**(①上传毛坯 ②用户指令style/room/prompt/比例 ③AI中间过程 vision_analysis_ok/enhanced_prompt/model/耗时 ④输出效果图 ⑤用户反馈)。安全路径解析(只allow input//output/，防遍历)、图损坏不崩。
  2. 示例数据 `data/sample_traces.jsonl`(3条，指向真实input/output图)：含**两个诊断亮点**——sess_A 重生成→满意的两次操作串联；sess_B `vision_analysis_ok=false`(静默降级)+房型做错的bad case。真实traces.jsonl存在则读真实、否则回退示例并挂横幅。**故意不写生产trace路径**，避免日后被import当真实数据。
  3. `config.py` 加 `TRACE_LOG_PATH`(读env,默认backend/data/traces.jsonl) + `SAMPLE_TRACES_PATH`。
- **验证**：全py_compile过；`_load_traces`回退示例3条、会话分组A2/B1正确；真实图解析且存在、越权路径(../etc、data/前缀)被拒；整UI导入OK；看板重启 http://localhost:8501 第7tab可见。
- **仍缺(要素④真正完整还差)**：①埋点部署上线(要动生产+等用户)才有真实数据；②中途节点记更全(现只记vision_ok/enhanced_prompt，分割/视觉原始返回未记=尚不够白盒)。**未push**。

### 2026-07-02 · 模块二第一刀：eval harness「骨架合体」（免费，本地测通）
- **背景**：用户看完模块二网课（eval harness 架构/执行环境/调试工具/控制变量）。用最后一张「Eval Harness 五大要素」(Anthropic 框架：①Loader筛选 ②Runner批量 ③环境隔离/可复现 ④Trace日志 ⑤Aggregator分维度) 逐条映射现有代码 → 结论：**零件基本都有，缺的是「串起来+接上」**。用户拍板先做免费的「骨架合体」(接通 ①②③⑤，④trace部署 与 生成式重跑 押后)。
- **动手前核到两个雷**（都躲过）：
  - (a) 旧 `runner.py` 写结果时只带 style/room_type/tags/split 四维 → **直接重跑会把 difficulty/intrinsic_difficulty 两个切片维度冲掉**。
  - (b) `intrinsic_difficulty` 存 pair **顶层**但**不是 ImagePair 字段**(from_dict 丢弃)；`difficulty` **源数据根本没有**(只在 eval_results，人工分反推)。→ 这俩维度 runner **无法从输入重算**，必须**合并写盘时保留既有结果的维度**。
- **做了（3 文件）**：
  1. 新建 `executor/aggregator.py`(要素⑤)：`aggregate()` 出总览 + 按 split/room_type/difficulty/intrinsic_difficulty/style/tags 分组；`to_markdown()` 每组按均值降序(最烂一眼可见)；产出 `data/eval_report.md`(人读)+`eval_report.json`(程序读)。
  2. 重写 `executor/runner.py`：`--split/--room-type/--difficulty/--intrinsic-difficulty/--tags` 筛 case 子集(①)；`scorer.score` 套 try/except **失败隔离**(单点报错记 None 继续不崩整轮)(②)；`--resume` 续跑；**合并写盘非破坏性**(保留既有富化维度+retired_metrics，只更新分数与基础属性)；`last_run` 快照(筛选/指标/mock/耗时/计数)存进结果文件(③)；`--dry-run`/`--report-only`/`--no-merge`。跑完自动出聚合报告(⑤)。
  3. `config.py` 加 `EVAL_REPORT_MD_PATH`/`EVAL_REPORT_JSON_PATH`。
- **验证(全程不碰真 eval_results，用临时副本)**：三文件 py_compile 过；`--report-only` 对真85条出6维报告正常；`--dry-run --intrinsic-difficulty extreme` 命中9(与分布吻合)；临时副本跑 `--room-type study` → 合并后仍85条、study分更新、**difficulty/intrinsic维度保留**、retired_metrics保留、last_run快照完整、未跑的pair_001分与维度不变；失败隔离：喂坏图→记None+n_errors=1+不崩+仍合并85。真实数据零污染复核通过。
- **一句话读数据**（免费副产品，来自新报告）：structural_fidelity 在各维度间**普遍平**(split 56.99~60.55 / 难度档 56.5~59.1)——再次印证它「聚焦结构单维、不随美学难度起伏」，模型好坏主因仍在美学/指令两维(没可信尺子)。
- **未 push**：本地 commit，因 origin 前还压着未推的 trace 第5步(用户「攒着」)，push 决策交用户。

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
