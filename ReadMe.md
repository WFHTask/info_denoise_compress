# VoiVerse - Web3 信息智能聚合与降噪系统

> 基于 TrendRadar 构建的 Web3 资讯自动化采集、降噪与推送系统

---

## ⚡ 快速启动

### 🚀 一键启动（推荐）

进入 `deploy` 文件夹，双击运行：
- **Windows**: `启动Web3.bat` ⭐
- **PowerShell**: `启动Web3.ps1`
- **Linux/Mac**: `启动Web3.sh`

**功能说明：**
- ✅ 自动检查 Python 环境
- ✅ 执行 Web3 资讯抓取
- ✅ 自动打开生成的报告页面

**报告位置：** `src/backend/TrendRadar/output/index.html`

### 📦 手动部署方式

**步骤 1：安装依赖**

```bash
cd src/backend/TrendRadar
pip install -r requirements.txt
```

**步骤 2：预览推送内容（不实际推送）**

```bash
python run_web3_push.py --dry-run
```

**步骤 3：正式运行**

```bash
python run_web3_push.py
```

📖 详细说明请查看 [START.md](START.md) 或 [部署中心](deploy/README.md)

---

## 📌 项目概述

本项目是 VoiVerse 平台的 Web3 信息聚合模块，旨在解决 Web3 领域信息**碎片化严重、24/7 全天候产出、信噪比极低**的问题。

系统能够从多个 Web3 媒体源自动采集资讯，通过关键词规则过滤垃圾信息（空投广告、带货推广等），保留核心信号（融资、安全事件、协议更新等），最终生成每日简报并推送至微信/Telegram。

---

## 🎯 任务目标

调研并选型最适合的开源 AI 框架，针对指定的 Web3 媒体源，实现一套能够**"压缩信息、提取信号、降低噪音"**的自动化推送流。

### 候选方案

| 方案 | 仓库 | 特点 |
|------|------|------|
| WiseFlow | [GitHub](https://github.com/TeamWiseFlow/wiseflow) | 智能监控与网页抓取，支持关注点配置 |
| **TrendRadar** ✅ | [GitHub](https://github.com/sansan0/TrendRadar) | 多平台热点聚合（35+平台），MCP 架构，支持微信/TG 推送 |
| nbot.ai | [官网](https://nbot.ai/) | AI 策展工具，自然语言描述需求 |

**最终选择：TrendRadar** - 详见 [选型报告](docs/selection-report.md)

---

## 📊 当前进展

### 交付物完成状态

| 序号 | 交付物 | 状态 | 完成度 | 文档位置 |
|------|-------|------|-------|---------|
| 1 | 选型报告 | ✅ 已完成 | 100% | [docs/selection-report.md](docs/selection-report.md) |
| 2 | 部署视频 | ✅ 已完成 | 100% | [运行演示部署视频.mp4](运行演示部署视频.mp4) |
| 3 | 运行演示 | ✅ 已完成 | 100% | [运行演示部署视频.mp4](运行演示部署视频.mp4) |
| 4 | 源代码/配置文件 | ✅ 已完成 | 90% | `src/backend/TrendRadar/` |

### 信息源接入状态

#### 目标信息源 (4个)

| 信息源 | 要求 | 接入方式 | 状态 |
|-------|------|---------|------|
| [Cointelegraph](https://cointelegraph.com) | 全球头部新闻 | RSS | ✅ 已接入 |
| [ME News](https://www.me.news) | 实时资讯 | 自定义爬虫 | ⚠️ 需 JS 渲染，待完善 |
| [ChainCatcher](https://www.chaincatcher.com) | 中文核心媒体 | 自定义爬虫 | ✅ 已接入 |
| [TechFlow 深潮](https://www.techflowpost.com) | 深度分析 | RSS (Substack) | ✅ 已接入 |

#### 补充信息源

为提升信息覆盖度，已接入以下国际 Web3 媒体：

| 信息源 | 类型 | 状态 | 说明 |
|-------|------|------|------|
| CoinDesk | RSS | ✅ 已接入 | 全球头部加密媒体 |
| The Block | RSS | ✅ 已接入 | 专业数据分析 |
| Decrypt | RSS | ✅ 已接入 | 主流加密新闻 |
| Bitcoin Magazine | RSS | ✅ 已接入 | 比特币专业媒体 |
| Blockworks | RSS | ✅ 已接入 | 机构级资讯平台 |

**配置位置：** `src/backend/TrendRadar/config/web3_sources.yaml`

---

## 📁 项目结构

```
VoiVerseProject/
├── README.md                          # 本文件 - 项目说明
├── START.md                           # 快速启动指南
├── check_env.py                       # 环境验证脚本
├── .gitignore
│
├── docs/                              # 📄 文档目录
│   ├── rules.md                       # Claude Code 使用规则
│   ├── selection-report.md           # 选型报告 ✅
│   ├── api-config-guide.md            # API 配置指南
│   ├── prompts.md                     # Prompt 合集
│   └── develop/
│       ├── design.md                  # 系统设计文档
│       ├── requirements.md            # 需求文档
│       ├── tasks.md                   # 开发任务清单
│       └── TODO.md                    # 待办计划
│
├── deploy/                            # 🚀 部署配置
│   ├── README.md                      # 部署指南 ✅
│   ├── 启动Web3.bat                   # Windows 启动脚本
│   ├── 启动Web3.ps1                   # PowerShell 启动脚本
│   └── 启动Web3.sh                     # Linux/Mac 启动脚本
│
└── src/
    └── backend/
        └── TrendRadar/                # 🔧 核心代码（基于 TrendRadar）
            ├── config/
            │   ├── config.yaml        # 主配置文件
            │   ├── web3_sources.yaml  # Web3 源 + 降噪规则
            │   └── frequency_words.txt # 关键词过滤配置
            ├── output/                 # 输出目录
            │   ├── index.html         # 主报告页面
            │   ├── web3/               # Web3 资讯数据
            │   └── news/               # 新闻数据
            ├── trendradar/
            │   └── crawler/
            │       └── web3/           # Web3 爬虫
            │           ├── chaincatcher.py  # ChainCatcher 爬虫 ✅
            │           ├── menews.py        # ME News 爬虫 ⚠️
            │           └── fetcher.py        # 通用抓取器
            ├── run_web3_push.py        # 主程序：抓取 + 推送
            ├── test_web3_crawler.py    # 测试脚本
            └── requirements.txt        # Python 依赖
```

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- pip

### 2. 安装依赖

```bash
cd src/backend/TrendRadar
pip install -r requirements.txt
```

### 3. 测试爬虫

```bash
python test_web3_crawler.py
```

### 4. 预览推送内容

```bash
python run_web3_push.py --dry-run
```

### 5. 配置推送渠道

编辑 `config/config.yaml`，配置企业微信或 Telegram：

```yaml
notification:
  enabled: true
  channels:
    wework:
      webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"
```

### 6. 正式运行

```bash
python run_web3_push.py
```

**命令参数说明：**

| 参数 | 说明 |
|------|------|
| `--dry-run` | 预览推送内容，不实际发送 |
| `--no-open` | 不自动打开报告页面 |
| `--test` | 仅测试抓取，不推送 |

详细部署说明请参考 [部署指南](deploy/README.md)

---

## 🔧 核心功能

### 降噪规则

系统通过关键词黑白名单实现内容降噪：

**过滤（黑名单）：**
- 空投类：空投、airdrop、免费领取、白嫖、撸毛
- 广告类：限时优惠、注册送、邀请码、推广链接
- 低质量：暴富、财富密码、百倍币、稳赚

**保留（白名单）：**
- 协议更新：升级、更新、发布、上线、主网
- 投融资：融资、投资、收购、IPO、估值
- 安全事件：漏洞、攻击、被盗、安全、黑客
- 监管政策：监管、政策、合规、牌照、法规
- 重要动态：ETF、SEC、财报、比特币、以太坊

配置位置：`src/backend/TrendRadar/config/web3_sources.yaml`

### 推送渠道

| 渠道 | 状态 | 配置位置 |
|------|------|---------|
| 企业微信 | ✅ 支持 | `config.yaml` → `notification.channels.wework` |
| Telegram | ✅ 支持 | `config.yaml` → `notification.channels.telegram` |
| 飞书 | ✅ 支持 | `config.yaml` → `notification.channels.feishu` |
| 钉钉 | ✅ 支持 | `config.yaml` → `notification.channels.dingtalk` |
| 邮件 | ✅ 支持 | `config.yaml` → `notification.channels.email` |

---

## 📋 待完成事项

| 优先级 | 任务 | 状态 | 预估时间 |
|-------|------|------|---------|
| 🔴 高 | 配置实际 Webhook URL | ⏳ 待完成 | 15-30 分钟 |
| 🔴 高 | 验证完整推送流程 | ⏳ 待完成 | 15 分钟 |
| 🔴 高 | 录制部署视频 | ⏳ 待完成 | 15 分钟 |
| 🔴 高 | 录制运行演示视频 | ⏳ 待完成 | 15 分钟 |
| 🟡 中 | 整理配置文件交付物 | ⏳ 待完成 | 15 分钟 |
| 🟢 低 | Docker 容器化部署 | ⏳ 待完成 | 30 分钟 |
| 🟢 低 | ME News 爬虫完善 (Playwright) | ⏳ 待完成 | 1-2 小时 |

详见 [待办计划](docs/develop/TODO.md)

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| [选型报告](docs/selection-report.md) | WiseFlow vs TrendRadar vs nbot.ai 对比分析 |
| [部署指南](deploy/README.md) | 完整的安装、配置、运行说明 |
| [设计文档](docs/develop/design.md) | 系统架构与接口设计 |
| [需求文档](docs/develop/requirements.md) | 功能需求与验收标准 |
| [待办计划](docs/develop/TODO.md) | 剩余任务与时间估算 |
| [Claude 规则](docs/rules.md) | AI 助手行为约束规则 |

---

## 🏷️ 技术栈

- **基础框架**: [TrendRadar](https://github.com/sansan0/TrendRadar)
- **语言**: Python 3.10+
- **数据采集**: requests, BeautifulSoup, feedparser
- **推送**: 企业微信 Webhook, Telegram Bot API
- **配置**: YAML
- **部署**: Docker (可选)

---

## 📄 许可证

本项目基于 [TrendRadar](https://github.com/sansan0/TrendRadar) 构建，遵循 MIT 许可证。

---

**最后更新：** 2026-01-10  
**维护者：** VoiVerse Team