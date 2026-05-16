#!/bin/bash
# Roommate AI 服务器部署脚本

set -euo pipefail

echo "=========================================="
echo "  Roommate AI 部署脚本"
echo "=========================================="

# 更新系统
echo "[1/8] 更新系统包..."
apt update && apt upgrade -y

# 安装必要工具
echo "[2/8] 安装必要工具..."
apt install -y git curl nginx python3 python3-pip python3-venv

# 安装 Node.js 18
echo "[3/8] 安装 Node.js..."
# TODO #65: curl | bash 存在供应链风险。后续 PR 改为：
# 下载脚本到本地 → 校验 sha256 → 再执行；或改用 NodeSource 的 apt 源 + GPG 校验。
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# 创建项目目录
echo "[4/8] 创建项目目录..."
mkdir -p /var/www/roommate
cd /var/www/roommate

# 克隆代码
echo "[5/8] 克隆代码..."
if [ -d ".git" ]; then
    git pull origin main
else
    git clone https://github.com/Frenkie99/Roommate-AI-interior.git .
fi

# 配置后端
echo "[6/8] 配置后端..."
cd /var/www/roommate/backend
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 创建/更新环境变量文件（幂等，#64）
# 1) 已存在则先备份，保留运维手工修改和已轮换的 key
# 2) 用 set_if_missing 追加缺失项，不再 truncate 覆盖
if [ -f .env ]; then
    cp .env ".env.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
touch .env

set_if_missing() {
    local key="$1"
    local value="$2"
    if ! grep -q "^${key}=" .env 2>/dev/null; then
        echo "${key}=${value}" >> .env
    fi
}

set_if_missing GRSAI_API_KEY "sk-3f112119d539422b89ee22440b31ebec"
set_if_missing GRSAI_API_URL "https://grsai.dakka.com.cn"

# .env 含 API key，限制为仅属主可读（#7）
chmod 600 .env
# 若 backend 以独立用户运行（见 start-backend.sh 中的 roommate 账户），
# 需把 .env 归属交给该用户，否则 systemd EnvironmentFile 读不到。
if id -u roommate >/dev/null 2>&1; then
    chown roommate:roommate .env
fi

# 构建前端
echo "[7/8] 构建前端..."
cd /var/www/roommate/frontend
npm install
npm run build

# 配置 Nginx
echo "[8/8] 配置 Nginx..."
# 已存在配置则先备份（#64）
NGINX_CONF=/etc/nginx/sites-available/roommate
if [ -f "$NGINX_CONF" ]; then
    cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi

# TODO #6: 添加 HTTPS server { listen 443 ssl; ... } 块。需先 certbot 申请证书。
# 当前 80 端口配置已加 X-Content-Type-Options / X-Frame-Options / Referrer-Policy，
# 但 HSTS 必须等 HTTPS 落地后再加，否则浏览器会拒绝降级到 HTTP。
cat > "$NGINX_CONF" << 'EOF'
server {
    listen 80;
    server_name _;

    # 安全响应头（#6）— HTTP/HTTPS 都生效
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # 前端静态文件
    location / {
        root /var/www/roommate/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        client_max_body_size 50M;
    }
}
EOF

# 启用站点
ln -sf /etc/nginx/sites-available/roommate /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "下一步：启动后端服务"
echo "运行: cd /var/www/roommate/backend && source venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000"
