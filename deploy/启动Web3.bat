@echo off
chcp 65001 >nul 2>&1
title Web3 信息聚合系统
echo ========================================
echo   TrendRadar Web3 信息聚合系统
echo   一键启动脚本
echo ========================================
echo.

cd /d "%~dp0"

REM 设置项目路径
set "PROJECT_DIR=%~dp0..\src\backend\TrendRadar"
set "OUTPUT_DIR=%PROJECT_DIR%\output"

echo [1/3] 检查环境...

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：Python 未安装！
    pause
    exit /b 1
)
echo ✅ Python 已安装

REM 检查项目目录
if not exist "%PROJECT_DIR%\run_web3_push.py" (
    echo ❌ 错误：找不到项目文件！
    echo    路径: %PROJECT_DIR%
    pause
    exit /b 1
)
echo ✅ 项目目录正确

echo.
echo [2/3] 执行 Web3 资讯抓取...

REM 检查是否已有报告（判断是否首次运行）
if exist "%OUTPUT_DIR%\index.html" (
    echo 📄 检测到已有报告，正在更新...
) else (
    echo 🆕 首次运行，正在生成报告...
    echo    （首次可能需要安装依赖，请稍候）
)

echo.
cd /d "%PROJECT_DIR%"
python run_web3_push.py --no-open

if errorlevel 1 (
    echo.
    echo ❌ 抓取失败，请检查网络连接或查看错误信息
    pause
    exit /b 1
)

echo.
echo [3/3] 打开报告页面...

cd /d "%~dp0"
if exist "%OUTPUT_DIR%\index.html" (
    echo ✅ 正在打开报告...
    start "" "%OUTPUT_DIR%\index.html"
) else (
    echo ⚠️ 报告文件未生成
    echo    路径: %OUTPUT_DIR%\index.html
)

echo.
echo ========================================
echo   ✅ 完成！
echo ========================================
echo.
echo 📊 报告路径: %OUTPUT_DIR%\index.html
echo.
echo 💡 提示:
echo    - 再次运行此脚本可更新资讯
echo    - 报告支持点击数据源筛选
echo.
pause
