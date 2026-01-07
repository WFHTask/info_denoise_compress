# 🚀 VoiVerse Web3 信息聚合系统 - 快速启动

## 一、环境准备

确保已安装 Python 3.10+

```bash
python --version
```

## 二、启动步骤

### 步骤 1：安装依赖

```bash
cd src/backend/TrendRadar
pip install -r requirements.txt
```

### 步骤 2：测试爬虫

```bash
python test_web3_crawler.py
```

### 步骤 3：预览推送内容（不实际推送）

```bash
python run_web3_push.py --dry-run
```

### 步骤 4：正式推送（需配置 Webhook）

1. 编辑 `src/backend/TrendRadar/config/config.yaml`
2. 找到 `notification.enabled` 改为 `true`
3. 填入企业微信 Webhook URL
4. 运行：

```bash
python run_web3_push.py
```

## 三、一键测试命令

**Windows:**
```cmd
cd src\backend\TrendRadar && python run_web3_push.py --dry-run
```

**Mac/Linux:**
```bash
cd src/backend/TrendRadar && python run_web3_push.py --dry-run
```

## 四、命令说明

| 命令 | 作用 |
|------|------|
| `python run_web3_push.py --test` | 只抓取，不推送 |
| `python run_web3_push.py --dry-run` | 抓取 + 预览推送内容 |
| `python run_web3_push.py` | 抓取 + 实际推送 |

## 五、相关文档

- [完整部署指南](deploy/README.md)
- [选型报告](docs/selection-report.md)
- [项目说明](README.md)