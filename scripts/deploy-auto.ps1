# 自动部署脚本 - 前端
param(
    [string]$Server = "47.76.239.100",
    [string]$Username = "root",
    [string]$RemoteDist = "/var/www/roommate/frontend/dist"
)

Write-Host "开始部署..." -ForegroundColor Green

# 1. 构建前端
Write-Host "正在构建前端..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\frontend"
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "构建失败!" -ForegroundColor Red
    exit 1
}
Write-Host "构建成功!" -ForegroundColor Green

# 2. 清空远程旧文件并上传新文件
Write-Host "正在上传..." -ForegroundColor Yellow
$target = "${Username}@${Server}:${RemoteDist}"

ssh "${Username}@${Server}" "rm -rf ${RemoteDist}/*"
scp -r dist/* $target

if ($LASTEXITCODE -ne 0) {
    Write-Host "上传失败!" -ForegroundColor Red
    exit 1
}

# 3. 重启 nginx
Write-Host "重启 nginx..." -ForegroundColor Yellow
ssh "${Username}@${Server}" "systemctl reload nginx"

Write-Host ""
Write-Host "部署完成!" -ForegroundColor Green
Write-Host "https://roommate-ai.cn/" -ForegroundColor Cyan
