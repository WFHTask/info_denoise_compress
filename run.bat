@echo off
chcp 65001 >nul
title VoiVerse Web3 信息聚合系统

echo.
echo ========================================
echo   VoiVerse Web3 信息聚合系统
echo ========================================
echo.
echo   1. 安装依赖
echo   2. 测试爬虫
echo   3. 预览推送内容 (不实际推送)
echo   4. 正式推送
echo   5. 环境检查
echo   6. 退出
echo.
echo ----------------------------------------

set /p choice=请选择操作 [1-6]:

if "%choice%"=="1" goto install
if "%choice%"=="2" goto test_crawler
if "%choice%"=="3" goto dry_run
if "%choice%"=="4" goto push
if "%choice%"=="5" goto check_env
if "%choice%"=="6" goto end

echo 无效选择，请重新运行
pause
goto end

:install
echo.
echo [安装依赖...]
cd src\backend\TrendRadar
pip install -r requirements.txt
echo.
echo [完成]
pause
goto end

:test_crawler
echo.
echo [测试爬虫...]
cd src\backend\TrendRadar
python test_web3_crawler.py
echo.
pause
goto end

:dry_run
echo.
echo [预览推送内容...]
cd src\backend\TrendRadar
python run_web3_push.py --dry-run
echo.
pause
goto end

:push
echo.
echo [正式推送...]
echo 注意：请确保已在 config/config.yaml 中配置 Webhook
echo.
cd src\backend\TrendRadar
python run_web3_push.py
echo.
pause
goto end

:check_env
echo.
echo [环境检查...]
python check_env.py
echo.
pause
goto end

:end
