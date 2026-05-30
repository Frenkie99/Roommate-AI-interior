---
name: "source-command-review-backend"
description: "审查后端 Python 代码的质量和安全性"
---

# source-command-review-backend

Use this skill when the user asks to run the migrated source command `review-backend`.

## Command Template

# 后端代码审查

审查 backend/ 目录下的所有 Python 代码，检查以下问题：

1. **API 安全性** - 检查输入验证、文件上传限制、路径遍历漏洞
2. **错误处理** - 是否有未捕获的异常、是否正确返回错误信息
3. **性能问题** - 异步处理是否正确、是否有阻塞操作
4. **代码规范** - 是否符合 PEP 8、命名是否清晰

输出格式：
- 问题严重程度（Critical/High/Medium/Low）
- 文件位置和行号
- 问题描述
- 修复建议和代码示例

---
**Last Updated**: April 10, 2026
