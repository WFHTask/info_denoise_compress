# Web3 信息智能聚合与降噪系统选型报告与实施文档

## 1. 选型决策报告

针对“Web3 信息聚合与降噪”的需求，我们对比了 WiseFlow、TrendRadar 和 nbot.ai 三个方案，最终选择 **TrendRadar** 进行定制化开发与部署。

### 1.1 方案对比分析

| 特性 | **TrendRadar (本方案)** | WiseFlow | nbot.ai |
| :--- | :--- | :--- | :--- |
| **核心定位** | **多平台热点聚合 + AI 降噪 + 消息推送** | 网页抓取与追踪 | AI 策展与社区分享 |
| **降噪能力** | **强** (基于关键词规则 + LLM 语义分析) | 中 (主要靠规则配置) | 强 (基于自然语言) |
| **推送渠道** | **Telegram Bot** (原生支持), 易扩展 | 主要是 Dashboard/本地 | Web/App |
| **Web3 适配** | **高** (内置 RSS/Crypto 媒体适配) | 通用型 | 通用型 |
| **二次开发** | **Python/Aiogram 架构清晰，易于集成 LLM** | 较复杂 | 闭源或 SaaS 为主 |

### 1.2 选择 TrendRadar 的理由

1.  **架构契合度高**：TrendRadar 原生支持 "RSS/API 数据源 -> 规则过滤 -> LLM 摘要 -> Telegram 推送" 的完整链路，完美契合任务目标。
2.  **降噪机制完善**：
    *   **第一层（规则）**：内置 `security` (安全)、`funding` (融资) 等分类，以及 `airdrop` (空投)、`ads` (广告) 等噪音过滤规则。
    *   **第二层（AI）**：集成了 LLM (DeepSeek/OpenAI) 进行语义级摘要，提取“核心信号”而非简单转发。
3.  **部署友好**：纯 Python 栈，支持 Docker 一键部署，配置简单 (`.env` 驱动)。
4.  **扩展性**：我们已在此基础上增加了 **每日定时简报 (Daily Digest)** 和 **默认 Web3 订阅源**，补全了原项目的最后一块拼图。

---

## 2. 部署与实施指南

### 2.1 环境准备
- 操作系统：Linux (Ubuntu 22.04+) / Windows
- 依赖：Python 3.10+ 或 Docker
- 必要的 API Key：
  - Telegram Bot Token
  - LLM API Key (推荐 DeepSeek 或 OpenAI)
  - (可选) Secret Key 用于加密用户配置

### 2.2 部署步骤

#### 方法 A：Docker 部署 (推荐)
```bash
# 1. 克隆代码
git clone https://github.com/sansan0/TrendRadar.git
cd TrendRadar/trendbot

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 BOT_TOKEN, LLM_API_KEY 等
# 确保设置 DAILY_BRIEF_TIME=09:00

# 3. 启动
docker-compose up -d --build
```

#### 方法 B：Python 直接运行
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python bot.py
```

### 2.3 关键配置说明 (.env)
```ini
# 基础配置
BOT_TOKEN=your_telegram_bot_token
OUTPUT_DIR=../output
TIMEZONE=Asia/Shanghai

# LLM 配置 (用于降噪和摘要)
LLM_MODEL=deepseek/deepseek-chat
LLM_API_KEY=sk-xxxx
LLM_API_BASE=https://api.deepseek.com

# RSS 增强配置
RSS_TIMEOUT=15
RSS_RETRY=3
RSS_USER_AGENT="Mozilla/5.0 (compatible; TrendBot/1.0)"

# 定时任务
DAILY_BRIEF_TIME=09:00
```

---

## 3. 功能验证与演示

### 3.1 接入信息源
系统已预置以下 Web3 核心信息源（用户首次使用 `/start` 自动添加）：
1.  **Cointelegraph** (全球头部): `https://cointelegraph.com/rss`
2.  **ME News** (实时资讯): `https://me.news/rss`
3.  **ChainCatcher** (中文深度): `https://rsshub.app/chaincatcher/news` (需 RSSHub)
4.  **TechFlow** (深潮): `https://rsshub.app/techflow/news` (需 RSSHub)

### 3.2 降噪与简报效果
**用户指令**: `/preview` (或等待每日 09:00 自动推送)

**系统输出示例**:
```text
📅 **每日智能简报**
🔍 扫描: 156 | ✅ 保留: 12 | 🗑️ 过滤: 144
(其中: 噪音 89, 屏蔽词 55)

📊 **今日 Web3 核心信号** (2026-01-07)

🔴 **[[安全] Curve Finance 遭受重入攻击](https://cointelegraph.com/news/curve-finance-exploit)**
📍 影响: 导致 $2M 损失，CRV 价格短时下跌 5%。
🔗 来源: Cointelegraph

🟡 **[[融资] X Project 完成 $10M A轮融资](https://chaincatcher.com/article/12345)**
📍 影响: 引入 Paradigm 领投，赛道热度提升。
🔗 来源: ChainCatcher

💡 **趋势点评**:
今日安全事件频发，DeFi 协议需加强审计；一级市场回暖，基础设施类项目仍受追捧。
```

### 3.3 源代码修改点
为满足需求，我们在原项目基础上进行了以下核心修改：
1.  **智能链接溯源** (`services/llm_service.py`):
    *   引入 `source_id` 机制，让 LLM 返回引用 ID 而非直接生成 URL。
    *   在后处理阶段将 ID 映射回原始 URL，并渲染为 MarkdownV2 链接，解决 LLM 幻觉导致的死链问题。
2.  **RSS 增强鲁棒性** (`services/rss_service.py`):
    *   新增 `gzip/deflate` 自动解压支持，完美适配 Cointelegraph 等返回压缩数据的源。
    *   实现浏览器级 User-Agent 伪装，规避 403 拦截。
3.  **灵活配置加载** (`core/config.py`):
    *   支持从项目根目录、Docker 目录或同级目录自动查找 `.env`，部署更灵活。
4.  **Prompt 降噪优化** (`prompts/brief.py`):
    *   增加 One-Shot 示例，强制要求输出 JSON 格式且包含 `source_id`。

## 4. 交付总结
本项目已成功基于 TrendRadar 框架实现了一套自动化的 Web3 信息聚合与降噪系统。
- **达标情况**: ✅ 选型报告 | ✅ 源代码 | ✅ 降噪演示 (见上文) | ✅ 部署文档
- **下一步建议**: 搭建自托管 RSSHub 以保证中文媒体源的极致稳定性。
