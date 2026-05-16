#!/bin/bash
# 后端服务启动脚本（使用 systemd）

set -euo pipefail

# 创建专用 roommate 用户（#5 #63），不再以 root 跑后端
if ! id -u roommate >/dev/null 2>&1; then
    useradd -r -s /bin/false -d /var/www/roommate roommate
fi

# 把工作目录交给 roommate
chown -R roommate:roommate /var/www/roommate

# 确保 ReadWritePaths 列出的目录存在
mkdir -p /var/www/roommate/output /var/www/roommate/input
chown -R roommate:roommate /var/www/roommate/output /var/www/roommate/input

# 创建 systemd 服务文件
cat > /etc/systemd/system/roommate-backend.service << 'EOF'
[Unit]
Description=Roommate AI Backend
After=network.target

[Service]
Type=simple
User=roommate
Group=roommate
WorkingDirectory=/var/www/roommate/backend
EnvironmentFile=/var/www/roommate/backend/.env
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 沙箱加固（#5 #63）
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadWritePaths=/var/www/roommate/output /var/www/roommate/input
MemoryMax=4G

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd 并启动服务
systemctl daemon-reload
systemctl enable roommate-backend
systemctl restart roommate-backend

echo "后端服务已启动！"
echo "查看状态: systemctl status roommate-backend"
echo "查看日志: journalctl -u roommate-backend -f"
