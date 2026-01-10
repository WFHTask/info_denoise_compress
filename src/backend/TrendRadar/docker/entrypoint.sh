#!/bin/sh
# Web3 TrendRadar Entrypoint Script
# 使用 run_web3_push.py 作为主程序

set -e

# 创建输出目录
mkdir -p /app/output

# 检查并安装必要的依赖（仅在缺失时安装一次）
# 使用文件标记避免重复检查
DEPS_CHECK_FILE="/app/.deps_installed"

if [ ! -f "$DEPS_CHECK_FILE" ]; then
    echo "📦 检查依赖..."
    MISSING_DEPS=""
    
    if ! python -c "import bs4" 2>/dev/null; then
        MISSING_DEPS="$MISSING_DEPS beautifulsoup4"
    fi
    
    if [ -n "$MISSING_DEPS" ]; then
        echo "📦 安装缺失的依赖:$MISSING_DEPS"
        pip install --quiet --no-cache-dir $MISSING_DEPS || true
    fi
    
    # 标记依赖已检查
    touch "$DEPS_CHECK_FILE"
fi

# 如果设置了 CRON_SCHEDULE，使用定时任务模式
if [ -n "$CRON_SCHEDULE" ]; then
    echo "⏰ 使用定时任务模式 (Cron: $CRON_SCHEDULE)"
    
    # 创建 crontab 文件
    echo "$CRON_SCHEDULE cd /app && python run_web3_push.py" > /tmp/crontab
    
    # 如果设置了立即运行，先执行一次
    if [ "$IMMEDIATE_RUN" = "true" ]; then
        echo "🚀 立即执行一次..."
        cd /app && python run_web3_push.py || true
    fi
    
    # 启动 supercronic
    echo "📅 启动定时任务服务..."
    exec supercronic /tmp/crontab
else
    # 单次运行模式
    echo "🚀 单次运行模式..."
    cd /app
    exec python run_web3_push.py
fi
