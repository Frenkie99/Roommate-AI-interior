# GitHub 自动部署说明

目标流程：

```text
PR 合并到 main -> GitHub Actions 登录阿里云 -> 服务器拉取 main -> 构建前端 -> 重启后端和 nginx
```

## 已按当前服务器信息配置的默认值

- 服务器用户：`admin`
- 项目路径：`/var/www/roommate`
- 部署分支：`main`
- 后端服务：`roommate-backend.service`

## GitHub Secrets

在 GitHub 仓库页面进入 `Settings -> Secrets and variables -> Actions -> New repository secret`，添加：

- `ALIYUN_HOST`：服务器 IP，例如 `47.76.239.100`
- `ALIYUN_SSH_KEY`：部署 SSH 私钥内容

可选：

- `ALIYUN_USER`：默认 `admin`
- `ALIYUN_PORT`：默认 `22`
- `ALIYUN_APP_DIR`：默认 `/var/www/roommate`
- `ALIYUN_BACKEND_SERVICE`：默认 `roommate-backend.service`

不要把服务器密码、私钥、`.env`、API Key 发到聊天或提交到仓库。

## 服务器一次性准备

让 `admin` 拥有项目目录写入权限：

```bash
sudo chown -R admin:admin /var/www/roommate
```

允许 GitHub 自动部署时重启指定服务，不需要输入密码：

```bash
echo 'admin ALL=(root) NOPASSWD: /usr/bin/systemctl restart roommate-backend.service, /usr/bin/systemctl reload nginx' | sudo tee /etc/sudoers.d/roommate-deploy
sudo chmod 440 /etc/sudoers.d/roommate-deploy
sudo visudo -cf /etc/sudoers.d/roommate-deploy
```

## SSH 密钥

生成专门给 GitHub Actions 使用的部署密钥后：

1. 公钥加入服务器 `admin` 用户的 `~/.ssh/authorized_keys`
2. 私钥内容填入 GitHub Secret：`ALIYUN_SSH_KEY`

## 手动触发

除了合并到 `main` 自动部署，也可以在 GitHub 的 `Actions -> Deploy to Aliyun -> Run workflow` 手动触发一次部署。
