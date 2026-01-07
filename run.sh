#!/bin/bash

# VoiVerse Web3 信息聚合系统 - 启动脚本

show_menu() {
    clear
    echo ""
    echo "========================================"
    echo "  VoiVerse Web3 信息聚合系统"
    echo "========================================"
    echo ""
    echo "  1. 安装依赖"
    echo "  2. 测试爬虫"
    echo "  3. 预览推送内容 (不实际推送)"
    echo "  4. 正式推送"
    echo "  5. 环境检查"
    echo "  6. 退出"
    echo ""
    echo "----------------------------------------"
}

install_deps() {
    echo ""
    echo "[安装依赖...]"
    cd src/backend/TrendRadar
    pip install -r requirements.txt
    echo ""
    echo "[完成]"
    read -p "按回车键继续..."
}

test_crawler() {
    echo ""
    echo "[测试爬虫...]"
    cd src/backend/TrendRadar
    python test_web3_crawler.py
    echo ""
    read -p "按回车键继续..."
}

dry_run() {
    echo ""
    echo "[预览推送内容...]"
    cd src/backend/TrendRadar
    python run_web3_push.py --dry-run
    echo ""
    read -p "按回车键继续..."
}

push() {
    echo ""
    echo "[正式推送...]"
    echo "注意：请确保已在 config/config.yaml 中配置 Webhook"
    echo ""
    cd src/backend/TrendRadar
    python run_web3_push.py
    echo ""
    read -p "按回车键继续..."
}

check_env() {
    echo ""
    echo "[环境检查...]"
    python check_env.py
    echo ""
    read -p "按回车键继续..."
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 主循环
while true; do
    show_menu
    read -p "请选择操作 [1-6]: " choice

    case $choice in
        1)
            install_deps
            cd "$SCRIPT_DIR"
            ;;
        2)
            test_crawler
            cd "$SCRIPT_DIR"
            ;;
        3)
            dry_run
            cd "$SCRIPT_DIR"
            ;;
        4)
            push
            cd "$SCRIPT_DIR"
            ;;
        5)
            check_env
            cd "$SCRIPT_DIR"
            ;;
        6)
            echo ""
            echo "再见！"
            exit 0
            ;;
        *)
            echo "无效选择，请重新选择"
            read -p "按回车键继续..."
            ;;
    esac
done
