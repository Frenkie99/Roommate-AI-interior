#!/bin/bash
# 后端服务启动脚本（使用 systemd）

# 创建 systemd 服务文件
cat > /etc/systemd/system/roommate-backend.service << 'EOF'
[Unit]
Description=Roommate AI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/roommate/backend
Environment="PATH=/var/www/roommate/backend/venv/bin"
ExecStart=/var/www/roommate/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd 并启动服务
systemctl daemon-reload
systemctl enable roommate-backend
systemctl start roommate-backend

echo "后端服务已启动！"
echo "查看状态: systemctl status roommate-backend"
echo "查看日志: journalctl -u roommate-backend -f"
