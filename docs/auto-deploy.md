# GitHub 自动部署说明

## 正常流程

确认改动 → 推送 main → 等 GitHub Actions 跑完 → 检查一次结果。

全程不需要打开阿里云远程连接或手动输入部署命令。

## 部署过程

推送 main 后，GitHub Actions 自动执行：

1. **CI 构建前端** — 在 GitHub 云端 runner 上 `npm ci && npm run build`，不在 1GB 服务器上构建
2. **上传前端** — 打包 dist 上传到服务器 `/tmp/frontend-dist.tar.gz`
3. **服务器部署** — `scripts/server-deploy.sh` 负责：
   - 备份 `input/`、`output/`、`backend/.env` 到 `/tmp/deploy-backup`
   - `git pull --ff-only` 拉取最新代码
   - 安装后端 Python 依赖（`pip install --prefer-binary -r requirements.txt`）
   - 解压前端 dist 到 `dist.new`
   - 重启后端服务 `roommate-backend.service`
   - 健康检查：轮询 `http://127.0.0.1:8000/health`（最多 10 次，间隔 2 秒）
   - 健康通过后原子切换前端：`mv dist dist.old && mv dist.new dist`
   - Reload nginx
4. **验证** — CI 再次检查后端健康端点和首页 200，核对 `.deployed-commit`

## 故障与回滚

如果后端健康检查失败：
- 自动回滚到部署前的 commit（`git reset --hard <PREV_COMMIT>`）
- 恢复 `input/`、`output/`、`.env` 从备份
- 重启后端，再次健康检查
- 前端 dist.new 被丢弃，旧 dist 保持不变
- 部署失败日志明确指出失败的阶段和恢复结果

## 查看线上版本

服务器上运行：
```bash
cat /var/www/roommate/.deployed-commit
```

或通过 GitHub Actions 的 "Verify deployment" 步骤输出查看。

## GitHub Secrets（一次性配置）

| Secret | 说明 | 示例 |
|--------|------|------|
| `ALIYUN_HOST` | 服务器 IP | `47.76.239.100` |
| `ALIYUN_SSH_KEY` | 部署 SSH 私钥 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `ALIYUN_USER` | SSH 用户（可选） | `admin` |
| `ALIYUN_PORT` | SSH 端口（可选） | `22` |
| `ALIYUN_APP_DIR` | 项目目录（可选） | `/var/www/roommate` |
| `ALIYUN_BACKEND_SERVICE` | systemd 服务名（可选） | `roommate-backend.service` |

## 服务器一次性准备

```bash
# 项目目录权限
sudo chown -R admin:admin /var/www/roommate

# sudoers：允许 GitHub Actions 重启服务和 reload nginx
echo 'admin ALL=(root) NOPASSWD: /usr/bin/systemctl restart roommate-backend.service, /usr/bin/systemctl is-active --quiet nginx, /usr/bin/systemctl reload nginx, /usr/sbin/nginx -t, /usr/sbin/nginx -s reload' | sudo tee /etc/sudoers.d/roommate-deploy
sudo chmod 440 /etc/sudoers.d/roommate-deploy
```

## 后端 /health 端点

部署脚本依赖 `http://127.0.0.1:8000/health` 返回 HTTP 200 JSON。
如果后端没有 `/health` 路由，需要新增一个：

```python
@router.get("/health")
async def health():
    return {"status": "ok"}
```

## 手动触发

除了推送 main 自动部署，也可以在 GitHub 仓库 `Actions → Deploy to Aliyun → Run workflow` 手动触发。
