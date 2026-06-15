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

# 创建环境变量文件（仅在不存在时生成模板，避免覆盖已有真实密钥）
if [ ! -f .env ]; then
cat > .env << 'EOF'
# API易平台 Key（图片生成 Gemini + LLM）：https://api.apiyi.com
APIYI_KEY=
LLM_APIYI_KEY=
CHAT_APIYI_KEY=
# 家具/区域分割（SAM3）：https://www.segmind.com
SEGMIND_API_KEY=
# 低内存服务器（~1GB）建议关闭知识库模型，避免后端 OOM
ENABLE_KNOWLEDGE_BASE=false
USE_LLM_PROMPT=true
EOF
echo "[提示] 已生成 backend/.env 模板，请填入真实 API Key 后再启动后端"
fi

# 构建前端
echo "[7/8] 构建前端..."
cd /var/www/roommate/frontend
npm install
npm run build

# 配置 Nginx（使用版本化的 deploy/nginx-roommate.conf）
echo "[8/8] 配置 Nginx..."
SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SETUP_DIR/nginx-roommate.conf" /etc/nginx/sites-available/roommate
echo "[提示] 该配置启用 HTTPS，请确保已放置 SSL 证书："
echo "       /etc/nginx/cert/roommate-ai.pem 与 /etc/nginx/cert/roommate-ai.key"

# 启用站点
ln -sf /etc/nginx/sites-available/roommate /etc/nginx/sites-enabled/roommate
rm -f /etc/nginx/sites-enabled/default
if nginx -t; then
    systemctl reload nginx
else
    echo "[警告] nginx 配置测试未通过（可能缺少 SSL 证书）。放置证书后再执行：nginx -t && systemctl reload nginx"
fi

echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "下一步：启动后端服务"
echo "运行: cd /var/www/roommate/backend && source venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000"
