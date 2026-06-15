# AI 智能室内设计平台

## 技术栈
- 前端：React 18 + Vite + TailwindCSS
- 后端：Python FastAPI + Uvicorn
- AI 服务：API易 Gemini + Segmind SAM3 + DeepSeek RAG
- 评测平台：Streamlit + PyTorch + OpenCV

## 项目结构
- frontend/src/components/ — React 组件
- frontend/src/pages/ — 页面
- frontend/src/services/ — API 调用封装
- backend/app/routes/ — API 路由
- backend/app/services/ — 业务逻辑（图片生成、分割、编辑）
- backend/app/models/ — 数据模型
- input/ — 用户上传的毛坯房原图
- output/ — AI 生成的效果图
- evals/ — 评测平台
  - evals/dataset/ — 数据集管理（采集、筛选、批量生成）
  - evals/scorer/ — 评分器（CLIP、结构保真度、LLM Judge）
  - evals/executor/ — 评测执行器
  - evals/ui/ — Streamlit 仪表盘
  - evals/data/ — 评测数据（metadata、eval_results）

## 开发规范
- 后端端口 8000，前端端口 5173
- Python 代码遵循 PEP 8
- React 组件使用函数式组件 + Hooks
- API 返回格式统一：{"code": 200, "message": "success", "data": {}}

## 注意事项
- .env 文件包含 API Key，不要提交到 Git
- SAM3 模型文件较大，不要修改
- 图片上传限制 10MB
- 用中文回复

# 项目协作规范

## 思维方式

运用第一性原理思考，拒绝经验主义和路径盲从，不要假设我完全清楚目标，保持审慎，
从原始需求和问题出发，若目标模糊请停下和我讨论，若目标清晰但路径非最优，请直接
建议更短、更低成本的办法。

## 回答结构

所有回答必须分为两个部分：
- **直接执行**：按照我当前的要求和逻辑，直接给出任务结果。
- **深度交互**：基于底层逻辑对我的原始需求进行“审慎挑战”。

## 安全红线

- **禁止未经确认的破坏性操作**：删除文件、删除函数/组件、`git reset --hard`、
  `git push --force`、`rm -rf`、drop/truncate table、无 WHERE 的 DELETE 等必须先告知用户并获得明确同意
- **修改优先于删除**：遇到“看起来没用”的代码，先确认调用链再动手；不确定时保留并注释，不要直接删
- **范围最小化**：只改任务要求的部分，不顺手清理周边代码、不删“顺眼觉得多余”的注释/变量/文件

## 工作流程

- 每次修改完成后必须 commit + push，不要积攒改动
- 改完代码必须验证：后端跑 API 测试，前端确认页面能加载
- 启动服务前检查 `.env` 配置
