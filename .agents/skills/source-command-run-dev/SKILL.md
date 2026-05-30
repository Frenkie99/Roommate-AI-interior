---
name: "source-command-run-dev"
description: "一键启动前后端开发服务器"
---

# source-command-run-dev

Use this skill when the user asks to run the migrated source command `run-dev`.

## Command Template

# 启动开发环境

按以下步骤启动项目：

1. 启动后端服务：
   - 进入 backend 目录
   - 运行 `python -m uvicorn app.main:app --reload --port 8000`

2. 启动前端服务：
   - 进入 frontend 目录
   - 运行 `npm run dev`

确保两个服务都成功启动，报告访问地址。

---
**Last Updated**: April 10, 2026
