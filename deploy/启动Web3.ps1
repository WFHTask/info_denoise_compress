# TrendRadar Web3 信息聚合系统 - 一键启动脚本
# PowerShell 版本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TrendRadar Web3 信息聚合系统" -ForegroundColor Cyan
Write-Host "  一键启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "[1/4] 检查 Docker 环境..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker 未安装"
    }
    Write-Host "✅ Docker 已安装: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 错误：Docker 未安装或未启动！" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 请确保：" -ForegroundColor Yellow
    Write-Host "   1. 已安装 Docker Desktop"
    Write-Host "   2. Docker Desktop 正在运行"
    Write-Host ""
    Read-Host "按 Enter 键退出"
    exit 1
}

Write-Host ""
Write-Host "[2/4] 进入项目目录..." -ForegroundColor Yellow
$dockerDir = Join-Path $ScriptDir "..\src\backend\TrendRadar\docker"
if (-not (Test-Path $dockerDir)) {
    Write-Host "❌ 错误：找不到项目目录！" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}
Set-Location $dockerDir
Write-Host "✅ 目录切换成功" -ForegroundColor Green

Write-Host ""
Write-Host "[3/4] 启动 Docker 容器..." -ForegroundColor Yellow
docker-compose down 2>&1 | Out-Null
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 错误：Docker 容器启动失败！" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}
Write-Host "✅ 容器启动成功" -ForegroundColor Green

Write-Host ""
Write-Host "[4/4] 等待服务初始化和生成报告..." -ForegroundColor Yellow
Write-Host "正在安装依赖和生成初始报告..." -ForegroundColor Cyan
Start-Sleep -Seconds 25

Write-Host "启动 Web 服务器..." -ForegroundColor Cyan
docker exec -d trendradar python manage.py start_webserver 2>&1 | Out-Null
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  🚀 启动成功！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 访问地址:" -ForegroundColor Cyan
Write-Host "   http://localhost:8080/" -ForegroundColor White
Write-Host "   http://localhost:8080/web3/" -ForegroundColor White
Write-Host ""
Write-Host "📝 说明:" -ForegroundColor Yellow
Write-Host "   - 使用 run_web3_push.py 抓取 Web3 资讯" -ForegroundColor Gray
Write-Host "   - 每 30 分钟自动更新（默认）" -ForegroundColor Gray
Write-Host "   - 支持 RSS 和 Web3 爬虫" -ForegroundColor Gray
Write-Host ""

Start-Process "http://localhost:8080/"

Write-Host "✅ 已完成！" -ForegroundColor Green
Write-Host ""
Write-Host "💡 常用命令：" -ForegroundColor Yellow
Write-Host "   - 查看日志: docker logs -f trendradar" -ForegroundColor Gray
Write-Host "   - 手动执行: docker exec trendradar python run_web3_push.py" -ForegroundColor Gray
Write-Host "   - 停止服务: cd src\backend\TrendRadar\docker; docker-compose down" -ForegroundColor Gray
Write-Host ""
Read-Host "按 Enter 键退出"
