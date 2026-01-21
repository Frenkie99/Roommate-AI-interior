#!/bin/bash
# Roommate AI 服务器部署脚本

set -e

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
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 创建环境变量文件
cat > .env << 'EOF'
GRSAI_API_KEY=sk-3f112119d539422b89ee22440b31ebec
GRSAI_API_URL=https://grsai.dakka.com.cn
EOF

# 构建前端
echo "[7/8] 构建前端..."
cd /var/www/roommate/frontend
npm install
npm run build

# 配置 Nginx
echo "[8/8] 配置 Nginx..."
cat > /etc/nginx/sites-available/roommate << 'EOF'
server {
    listen 80;
    server_name _;

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
