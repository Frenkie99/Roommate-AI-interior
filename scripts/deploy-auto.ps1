# PowerShell 自动部署脚本
# 需要安装 WinSCP: https://winscp.net/

param(
    [string]$Server = "47.76.239.100",
    [string]$Username = "root",
    [string]$RemotePath = "/var/www/roommate/frontend/",
    [string]$LocalPath = "frontend\dist"
)

Write-Host "开始自动部署到生产环境..." -ForegroundColor Green

# 1. 构建前端
Write-Host "正在构建前端..." -ForegroundColor Yellow
Set-Location frontend
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "前端构建失败！" -ForegroundColor Red
    exit 1
}

Write-Host "前端构建成功！" -ForegroundColor Green

# 2. 检查 WinSCP 是否安装
try {
    $winscp = Get-Command WinSCP.exe -ErrorAction Stop
} catch {
    Write-Host "未找到 WinSCP，请先安装: https://winscp.net/" -ForegroundColor Red
    Write-Host "或者使用手动部署方式" -ForegroundColor Yellow
    exit 1
}

# 3. 使用 WinSCP 上传文件
Write-Host "正在上传文件到服务器..." -ForegroundColor Yellow

try {
    # WinSCP 脚本
    $script = @"
option batch abort
option confirm off
open sftp://$Username@$Server/
cd "$RemotePath"
rm *
lcd "$LocalPath"
put *
exit
"@

    $script | Out-File -FilePath "temp_script.txt" -Encoding ASCII
    
    & WinSCP.exe /script=temp_script.txt
    
    Remove-Item "temp_script.txt"
    
    Write-Host "文件上传成功！" -ForegroundColor Green
} catch {
    Write-Host "文件上传失败: $_" -ForegroundColor Red
    exit 1
}

# 4. 重启 nginx（通过 SSH）
Write-Host "正在重启 nginx..." -ForegroundColor Yellow

try {
    $sshCommand = "ssh $Username@$Server 'systemctl reload nginx'"
    Invoke-Expression $sshCommand
    Write-Host "nginx 重启成功！" -ForegroundColor Green
} catch {
    Write-Host "nginx 重启失败，请手动执行: ssh $Username@$Server 'systemctl reload nginx'" -ForegroundColor Yellow
}

Write-Host "部署完成！" -ForegroundColor Green
Write-Host "访问 https://roommate-ai.cn/ 查看更新效果" -ForegroundColor Cyan
Write-Host ""
Write-Host "如果遇到问题，请联系技术支持" -ForegroundColor Yellow
