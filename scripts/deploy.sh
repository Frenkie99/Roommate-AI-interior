#!/bin/bash

# 部署脚本 - 更新生产环境
# 目标服务器: 47.76.239.100
# 域名: https://roommate-ai.cn/

echo "开始部署到生产环境..."

# 1. 构建前端
echo "正在构建前端..."
cd frontend
npm run build

if [ $? -ne 0 ]; then
    echo "前端构建失败！"
    exit 1
fi

echo "前端构建成功！"

# 2. 备份当前版本
echo "备份当前版本..."
ssh root@47.76.239.100 "cd /var/www/roommate && cp -r frontend frontend_backup_$(date +%Y%m%d_%H%M%S)"

# 3. 上传新版本
echo "上传新版本到服务器..."
scp -r dist/* root@47.76.239.100:/var/www/roommate/frontend/

# 4. 重启nginx（如果需要）
echo "重启nginx..."
ssh root@47.76.239.100 "systemctl reload nginx"

echo "部署完成！"
echo "访问 https://roommate-ai.cn/ 查看更新效果"
