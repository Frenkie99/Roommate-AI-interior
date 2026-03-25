#!/bin/bash
# 服务器端部署脚本 - 在服务器上执行

echo "开始更新生产环境..."

# 进入项目目录
cd /var/www/roommate

# 拉取最新代码
echo "拉取最新代码..."
git pull origin main

# 进入前端目录并安装依赖
echo "安装前端依赖..."
cd frontend
npm install

# 构建生产版本
echo "构建前端..."
npm run build

# 复制构建文件到 nginx 目录（如果需要）
# cp -r dist/* /var/www/html/roommate/

# 重启 nginx
echo "重启 nginx..."
systemctl reload nginx

echo "部署完成！"
echo "访问 https://roommate-ai.cn/ 查看效果"
