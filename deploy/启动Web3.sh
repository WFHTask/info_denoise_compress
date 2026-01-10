#!/bin/bash
# TrendRadar Web3 信息聚合系统 - 一键启动脚本
# Linux/Mac 版本

echo "========================================"
echo "  TrendRadar Web3 信息聚合系统"
echo "  一键启动脚本"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[1/4] 检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：Docker 未安装或未启动！"
    echo ""
    echo "💡 请确保："
    echo "   1. 已安装 Docker"
    echo "   2. Docker 服务正在运行"
    echo ""
    read -p "按 Enter 键退出"
    exit 1
fi
echo "✅ Docker 已安装: $(docker --version)"

echo ""
echo "[2/4] 进入项目目录..."
DOCKER_DIR="$SCRIPT_DIR/../src/backend/TrendRadar/docker"
if [ ! -d "$DOCKER_DIR" ]; then
    echo "❌ 错误：找不到项目目录！"
    read -p "按 Enter 键退出"
    exit 1
fi
cd "$DOCKER_DIR"
echo "✅ 目录切换成功"

echo ""
echo "[3/4] 启动 Docker 容器..."
docker-compose down >/dev/null 2>&1
docker-compose up -d

if [ $? -ne 0 ]; then
    echo "❌ 错误：Docker 容器启动失败！"
    read -p "按 Enter 键退出"
    exit 1
fi
echo "✅ 容器启动成功"

echo ""
echo "[4/4] 等待服务初始化和生成报告..."
echo "正在安装依赖和生成初始报告..."
sleep 25

echo "启动 Web 服务器..."
docker exec -d trendradar python manage.py start_webserver >/dev/null 2>&1
sleep 3

echo ""
echo "========================================"
echo "  🚀 启动成功！"
echo "========================================"
echo ""
echo "🌐 访问地址:"
echo "   http://localhost:8080/"
echo "   http://localhost:8080/web3/"
echo ""
echo "📝 说明:"
echo "   - 使用 run_web3_push.py 抓取 Web3 资讯"
echo "   - 每 30 分钟自动更新（默认）"
echo "   - 支持 RSS 和 Web3 爬虫"
echo ""

# 根据操作系统打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "http://localhost:8080/"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:8080/"
    elif command -v gnome-open &> /dev/null; then
        gnome-open "http://localhost:8080/"
    else
        echo "💡 请手动打开浏览器访问: http://localhost:8080/"
    fi
fi

echo ""
echo "✅ 已完成！"
echo ""
echo "💡 常用命令："
echo "   - 查看日志: docker logs -f trendradar"
echo "   - 手动执行: docker exec trendradar python run_web3_push.py"
echo "   - 停止服务: cd src/backend/TrendRadar/docker && docker-compose down"
echo ""
read -p "按 Enter 键退出"
