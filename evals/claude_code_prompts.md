# 评测平台搭建：Claude Code 四步走 Prompt 投放指南

本指南专为应对突击型工程任务设计，采用“切香肠”式增量开发策略，帮助你快速、稳定地使用 Claude Code 搭建包含“数据集、评分器、执行器与可视化 UI”的完整评测平台。

---

## 第一步：初始化项目骨架与构建 Mock 数据集

**目标**：完成基础目录创建，并生成带有元数据（Metadata）的假图片，为后续的数据流转提供基础物料，避免过早陷入真实文件读取的泥潭。

**复制以下指令发送给 Claude Code：**

> 读取 `docs/eval_guidelines.md` 的架构思路。我现在需要搭建一个可视化的评测平台。请先执行以下初始化任务：
> 1. 在根目录创建基础的项目结构：`dataset/`, `scorer/`, `executor/`, `ui/` 和 `data/`。
> 2. 编写一个 Python 脚本 `scripts/generate_mock_data.py`。该脚本使用 PIL 库在 `data/images/` 目录下生成 20 张带有序号和颜色背景的假图片（10张模拟原图，10张模拟生成图）。
> 3. 脚本需同时生成一个 `data/metadata.json` 文件，为这10组图片随机分配标签（如：标签包含 'standard', 'corner_case', 'dark_light'）并记录图片路径。
> 请只写这个脚本并执行它，确认生成了图片和 JSON 数据。

---

## 第二步：构建评测核心引擎

**目标**：将产品三要素（数据集、评分器、执行器）转化为 Python 面向对象的代码结构。本步骤强制要求使用 Mock 函数，避开复杂的真实 API 调用带来的网络或鉴权阻碍。

**复制以下指令发送给 Claude Code（须确保第一步已成功）：**

> 基于刚才生成的 `metadata.json` 和假图片，现在我们来实现核心引擎：
> 1. **数据集 (dataset.py):** 编写 `DatasetLoader` 类，负责读取 `metadata.json`，并能根据标签（tags）返回相应的图像对（原图和生成图路径）。
> 2. **评分器 (scorer.py):** 编写 `Evaluator` 类，根据 `eval_guidelines.md`，包含三个 Mock 打分函数：`calculate_iou()`, `calculate_fid()`, `calculate_clip_score()`。不要接入真实模型，直接使用 `random` 库返回合理范围内的浮点数即可。
> 3. **执行器 (executor.py):** 编写 `Runner` 类，它将 `DatasetLoader` 和 `Evaluator` 组合起来。遍历数据集，调用打分函数，最后将所有结果（包含图片路径、标签、各项得分）导出为一个扁平化的结构字典，并保存为 `data/eval_results.json`。
> 请按顺序编写并执行 `executor.py`，确保正确输出了 `eval_results.json` 文件。

---

## 第三步：搭建 Streamlit 可视化数据面板（MVP 版本）

**目标**：开发前端 UI，实现数据集的“可排序”和“可筛选”功能。

**复制以下指令发送给 Claude Code（须确保第二步成功生成了 json）：**

> 引擎已经跑通，现在我们需要在 `ui/app.py` 中使用 Streamlit 搭建可视化面板。请读取 `data/eval_results.json` 并实现以下功能：
> 1. **侧边栏筛选 (Filter):** 在侧边栏提供多选框或下拉菜单，允许用户根据图片标签（如 'corner_case'）筛选数据。同时提供滑动条，允许用户过滤出 FID 得分大于某个值的数据。
> 2. **可排序数据表 (Sortable Table):** 在主界面顶部使用 `st.dataframe` 展示筛选后的数据结果，确保表格的列名清晰（包含文件名、标签、各项得分），且点击表头可以对数据进行正序/倒序排序。
> 请编写代码后，告诉我如何在你终端启动这个 Streamlit 应用。

---

## 第四步：实现 Badcase/Goodcase 的图像对比可视化

**目标**：完善界面的视觉呈现，能够在筛选出特定数据后，直观地对比原图和生成图及各项指标。

**复制以下指令发送给 Claude Code：**

> Streamlit 基础表格已经有了。现在请在 `ui/app.py` 中补充具体的图像可视化逻辑：
> 当用户在界面的表格中选择（或点击）某一行具体数据时（或者直接遍历筛选后的数据展示前 5 条），在表格下方使用 `st.columns` 展示这组数据的视觉对比：
> 左边列展示‘原图’，中间列展示‘生成的渲染图’，右边列使用雷达图、进度条或醒目的 Markdown 文本展示该组数据的具体得分（IoU, FID, CLIP Score）。
> 目标是让我能直观地进行 badcase 分析。

---

### 💡 避坑执行指南：

1. **严格按顺序执行：** 只有确认上一步完全跑通（例如成功生成了 `.json` 文件或正确输出了 Mock 图像），再发送下一步指令。
2. **缺什么装什么：** 遇到 `ModuleNotFoundError` 报错，直接下达指令补充：“请帮我执行 `pip install streamlit pandas pillow`”。
3. **高频回滚保平安：** 任何一步代码被改崩且连续两次对话无法修复，不要纠缠，果断使用 `git reset --hard` 回滚到上一个稳定版本重新提问。