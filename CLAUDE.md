# AI 智能室内设计平台

## 技术栈
- 前端：React 18 + Vite + TailwindCSS
- 后端：Python FastAPI + Uvicorn
- AI 服务：API易 Gemini + Segmind SAM3 + DeepSeek RAG

## 项目结构
- frontend/src/components/ — React 组件
- frontend/src/pages/ — 页面
- frontend/src/services/ — API 调用封装
- backend/app/routes/ — API 路由
- backend/app/services/ — 业务逻辑（图片生成、分割、编辑）
- backend/app/models/ — 数据模型
- input/ — 用户上传的毛坯房原图
- output/ — AI 生成的效果图

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
