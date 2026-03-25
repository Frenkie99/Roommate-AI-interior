@echo off
echo 开始部署到生产环境...

REM 1. 构建前端
echo 正在构建前端...
cd frontend
call npm run build

if %errorlevel% neq 0 (
    echo 前端构建失败！
    pause
    exit /b 1
)

echo 前端构建成功！

REM 2. 使用pscp上传文件（需要安装PuTTY）
echo 上传新版本到服务器...
echo 请确保已安装 PuTTY 并配置好 SSH 密钥

REM 这里需要您手动执行或配置自动上传
echo.
echo 手动上传步骤：
echo 1. 使用 FileZilla 或其他FTP工具连接到 47.76.239.100
echo 2. 将 frontend\dist 目录下的所有文件上传到 /var/www/roommate/frontend/
echo 3. 在服务器上执行: systemctl reload nginx
echo.

echo 构建文件位置: %cd%\dist\
echo 请手动上传后访问 https://roommate-ai.cn/ 查看效果
pause
