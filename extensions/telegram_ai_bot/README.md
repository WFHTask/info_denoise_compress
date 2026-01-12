# TrendBot (Telegram Extension)

- This is an OPTIONAL extension for info_denoise_compress.
- It does NOT modify the core pipeline.
- It runs as a standalone Telegram bot.

## 功能总览

- 个性化新闻简报
  - 优先级排序（安全/融资/协议/监管）
  - 智能链接溯源：简报标题直达原始新闻链接
  - 屏蔽/白名单关键词
  - 智能噪音过滤（空投/广告/教程等）
- 自然语言配置
  - 聊天即可修改偏好或生成简报（LiteLLM 支持 DeepSeek/OpenAI/Claude）
- RSS 订阅管理
  - 添加/移除/查看订阅源
  - 单源立即抓取与后台周期抓取
  - 支持 Gzip/Deflate 压缩流自动处理

## 🚀 Quick Start

首先进入插件目录：
```bash
cd extensions/telegram_ai_bot
cp .env.example .env
# 编辑 .env 填入 BOT_TOKEN
```

### 方式 A: 使用 uv (推荐)
[uv](https://github.com/astral-sh/uv) 是极速 Python 包管理器。

```bash
# 1. 初始化环境并同步依赖
uv sync

# 2. 运行 Bot
uv run bot.py
```

### 方式 B: 使用 venv (标准)
使用 Python 标准工具链。

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行 Bot
python bot.py
```

## 指令列表

- /start：查看状态与指令列表
- /pref：调整简报优先级
- /block <关键词>：添加屏蔽关键词
- /allow <关键词>：添加白名单关键词
- /noise <on/off>：开关智能降噪
- /preview：生成并发送简报
- RSS
  - /add_rss <url>：添加订阅并试抓取
  - /remove_rss <url>：移除订阅
  - /list_rss：查看订阅列表

## 自然语言示例

- 只看融资，屏蔽 meme
- 生成今日简报
- 订阅这个 RSS：https://example.com/feed.xml
- 我要关闭降噪

## Advanced Configuration

```env
# Telegram Bot Token（必填）
BOT_TOKEN=your_telegram_bot_token

# LLM 配置（按需）
LLM_MODEL=deepseek/deepseek-chat
LLM_API_KEY=sk-xxxx
LLM_API_BASE=https://api.deepseek.com

# 网络代理（选填）
PROXY_URL=http://127.0.0.1:7890

# RSS UA（建议设置以提升兼容性）
RSS_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# 本地加密（可选，用于降低误用风险；不替代生产级密钥管理方案）
SECRET_KEY=please_set_a_strong_secret
```

## 兼容性与边界

- 与主项目的数据对接：
  - 可对接主项目的聚合输出（若存在且约定目录/接口稳定）。
  - 当前版本默认基于 RSS 数据源运行，不依赖主项目内部数据库。
- 运行模式：
  - 作为独立的 Telegram Bot 运行；不修改 info_denoise_compress 的核心管线。

## 技术栈（压缩版）

- Python 3.10+
- Aiogram 3.x（Telegram Bot）
- APScheduler（定时任务）
- LiteLLM（统一 LLM 接口）
- FeedParser（RSS）
- SQLite（轻量本地存储）
- Telegram MarkdownV2（消息格式渲染与转义）
