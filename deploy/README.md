# TrendRadar Web3 信息聚合系统 - 快速启动

## 🚀 一键启动

### Windows 用户（推荐）
直接双击：**`启动Web3.bat`** ⭐

### PowerShell 用户
运行：`启动Web3.ps1`

### Linux/Mac 用户
```bash
cd deploy
chmod +x 启动Web3.sh
./启动Web3.sh
```

## 📋 脚本说明

所有平台都使用相同的脚本 `启动Web3.bat/ps1/sh`：

**功能**：
- ✅ 自动检查 Docker 环境
- ✅ 启动 Docker 容器（使用 `run_web3_push.py`）
- ✅ 自动安装依赖和生成初始报告
- ✅ 启动 Web 服务器
- ✅ 自动打开浏览器访问 http://localhost:8080/

## 🌐 访问地址

启动成功后访问：
- **主页**: http://localhost:8080/
- **Web3 汇总**: http://localhost:8080/web3/

## ✨ 功能说明

- **数据来源**：RSS（Cointelegraph）+ Web3 爬虫（ChainCatcher、ME News）
- **定时任务**：每 30 分钟自动抓取一次（默认）
- **数据保存**：容器内的 `/app/output/web3/` 目录

## 💡 常用命令

```bash
# 查看日志
docker logs -f trendradar

# 手动执行一次抓取
docker exec trendradar python run_web3_push.py

# 停止服务
cd src\backend\TrendRadar\docker
docker-compose down

# 重启服务
docker-compose restart trendradar
```

## 🔧 环境要求

- Windows 10/11 或 Linux/Mac
- Docker Desktop 已安装并运行
- 端口 8080 可用

## 📞 故障排除

1. **Docker 未启动**：请先启动 Docker Desktop
2. **端口被占用**：关闭占用 8080 端口的程序
3. **查看日志**：`docker logs trendradar`

---
*最后更新：2026-01-10*
