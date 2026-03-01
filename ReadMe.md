# Web3 Daily Digest

> AI 驱动的 Web3 个性化信息聚合服务

每天自动抓取并筛选 Web3 信息，通过 AI 生成符合你偏好的个性化简报，节省 2+ 小时阅读时间。

## 研发与发布规范（精简）

- 发布与回滚流程：`RELEASE_SOP.md`
- 测试门禁清单：`QA_GATE.md`

## 核心特性

### AI 个性化筛选
- 3 轮 AI 对话式注册，深度理解用户偏好
- **两阶段筛选算法**（v1.5.0）：Stage 1 分批粗筛 → Stage 2 精选去重
- 两步处理流程：筛选（英文 prompt）→ 翻译（语言适配）
- 4 层内容分级：必读事件 / 行业大局 / 用户推荐 / 其他更新
- 跨源内容去重 + 来源多样性保证

### 智能反馈闭环
- 整体反馈（有帮助/没帮助）
- 单条反馈（👍/不感兴趣 按钮）
- 动态更新用户画像（固定篇幅，精细化描述），用户越用越精准
- 反馈趋势分析（近 30 天）

### 管理员控制台
- 白名单管理（增删查 + 开关）
- 多管理员支持（环境变量配置）
- AI 筛选分批处理（大数据量自动分批，避免超限）
- **📊 数据分析面板**（v1.4.0 新增）
  - 用户行为埋点（反馈、设置变更、信息源增删等）
  - 统计概览（事件数、活跃用户、满意度）
  - 运营洞察（优化建议 + 流失预警）
- **Plan 配置面板**（v1.7.0 新增）— Free/Pro 功能和限额管理
- **信息源健康监控** — RSS 源状态看板 + AI 自动修复

### 多信息源聚合
- Twitter 账号监控（通过 RSS URL 添加，支持 RSSHub 转换）
- 网站 RSS 订阅（支持自动检测）
- 每用户独立信息源配置 + 单条启用/禁用
- 批量导入默认信息源

### 群聊支持（v1.7.0 新增）
- Bot 可加入 Telegram 群组，定时推送公共简报
- 群管理员 `/setup` 配置关注领域和推送时间
- 群成员可私聊 Bot 配置个人偏好

### Free / Pro 版（v1.7.0 新增）
- Free：公共信息源 + 每日推送
- Pro：自定义信息源 + 自定义推送间隔（最短 1 小时）
- 管理员可灵活配置各功能的免费/付费属性

### AI 智能助手
- 自然语言对话（支持联网搜索）
- 读取最近 3 天推送内容作为上下文
- 可配置对话历史保留天数（0/1/2 天）
- 基于用户画像的个性化回答
- 支持多 LLM 提供商（Gemini / OpenAI）

### 多语言支持
- 自动检测用户 Telegram 语言设置
- UI 界面支持 4 种语言（中/英/日/韩），其他语言 AI 自动翻译
- 内容翻译支持 20+ 种语言（中/英/日/韩/俄/西/法/德/越/泰等）
- 用户可在设置页面手动切换语言偏好
- 保持原始链接，翻译标题和摘要

### 价值可感知
- 每日统计（信息源数 / 扫描条数 / 精选条数）
- 筛选率展示（节省时间可视化）
- 自然语言画像描述（用户偏好透明化）

---

## 功能概览

```
用户注册 → AI 对话收集偏好 → 每日自动抓取 → AI 智能筛选 → 生成简报 → Telegram 推送
                                    ↑                                         ↓
                                    └──────── AI 分析反馈，更新用户画像 ←──────┘
```

### Bot 命令

| 命令 | 功能 |
|------|------|
| `/start` | 主菜单（新用户进入注册流程，管理员显示控制台入口） |
| `/help` | 帮助信息 |
| `/settings` | 偏好设置管理 |
| `/sources` | 信息源管理（添加/删除/启用/禁用） |
| `/setup` | 群聊配置（仅群管理员，v1.7.0 新增） |
| `/stats` | 查看统计（简报数据+反馈趋势） |
| `/clear` | 清空对话历史 |
| `/test` | 手动触发抓取（仅管理员） |
| `/testprofile` | 手动触发画像更新（仅管理员） |

**管理员功能**（通过主菜单「管理员控制台」按钮访问）：
- 📊 数据分析（用户行为统计 + 运营建议）
- 白名单开关（启用/禁用访问控制）
- 查询白名单（显示用户详细信息）
- 添加/删除白名单用户

---

## 技术栈

| 技术层 | 选型 | 说明 |
|--------|------|------|
| **LLM 引擎** | Gemini / OpenAI / Kimi | 支持 Gemini 3 Pro、GPT-4 系列、Kimi K2 Thinking |
| **Bot 框架** | python-telegram-bot v22.0 | 官方推荐库 + 定时任务 + 对话流 |
| **RSS 抓取** | feedparser + httpx | 异步抓取 + 自动去重 |
| **数据存储** | JSON 文件 | MVP 轻量方案 + 多用户隔离 |
| **部署** | Docker Compose | 一键部署 + 数据卷持久化 |

---

## 项目结构

```
info_denoise_compress/
├── bot/                          # Telegram Bot
│   ├── main.py                   # 入口 + 定时任务 + handler 注册
│   ├── config.py                 # 环境变量配置 + 默认信息源解析
│   ├── handlers/                 # 用户交互层
│   │   ├── start.py              # 注册流程（3轮AI对话）+ 主菜单 + 统计
│   │   ├── chat.py               # AI 对话（联网+上下文+每日清理）
│   │   ├── feedback.py           # 反馈收集（整体+单条）
│   │   ├── sources.py            # 信息源管理（增删查）
│   │   ├── settings.py           # 偏好设置管理
│   │   └── admin.py              # 管理员控制台（白名单+数据分析）
│   ├── services/                 # 业务逻辑层
│   │   ├── llm_provider.py       # LLM 抽象接口
│   │   ├── llm_factory.py        # LLM 工厂 + 统一重试机制
│   │   ├── gemini_provider.py    # Gemini API 实现
│   │   ├── openai_provider.py    # OpenAI API 实现
│   │   ├── digest_processor.py   # 简报处理（单用户）
│   │   ├── rss_fetcher.py        # RSS 抓取（ID 去重）
│   │   ├── content_filter.py     # AI 筛选逻辑
│   │   ├── report_generator.py   # 简报生成（多语言）
│   │   └── profile_updater.py    # 反馈学习闭环（每日更新）
│   ├── utils/                    # 工具层
│   │   ├── json_storage.py       # 数据存储 + 白名单管理 + 埋点追踪
│   │   ├── telegram_utils.py     # Telegram 工具（限流器等）
│   │   ├── prompt_loader.py      # Prompt 模板加载
│   │   └── auth.py               # 白名单权限装饰器
│   ├── prompts/                  # Prompt 模板
│   │   ├── onboarding_*.txt      # 注册流程（3轮）
│   │   ├── filtering.txt         # 内容筛选（4层分级）
│   │   ├── translate.txt         # 语言适配（独立翻译）
│   │   ├── report.txt            # 简报生成
│   │   └── *_update.txt          # 画像/设置更新
│   ├── tests/
│   │   └── test_all_modules.py   # 自动化测试
│   ├── scripts/
│   │   └── generate_analytics_report.py  # 运营报表生成脚本
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── .gitignore
│
├── data/                         # 数据存储 (JSON)
│   ├── users.json                # 用户基本信息
│   ├── user_sources/             # 每用户信息源配置
│   ├── profiles/                 # 用户画像
│   ├── feedback/                 # 反馈记录（按日期）
│   ├── daily_stats/              # 每日统计（每用户子目录）
│   ├── raw_content/              # 原始抓取内容（每用户子目录）
│   ├── prefetch_cache/           # 预抓取缓存（解决 RSS 时效问题）
│   ├── events/                   # 用户行为事件（按月 JSONL 文件）
│   ├── analytics/                # 运营报表输出
│   └── logs/                     # 日志文件
│
├── docker-compose.yml            # Docker 一键部署配置
└── README.md                     # 本文件
```

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/WFHTask/info_denoise_compress.git
cd info_denoise_compress
git checkout beta1.0
```

### 2. 配置环境变量

```bash
cp bot/.env.example bot/.env
```

编辑 `bot/.env`，填写以下**必填项**：

```bash
# Telegram Bot Token（必填）
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# 管理员 Telegram ID（必填，多个用逗号分隔）
ADMIN_TELEGRAM_IDS=123456789

# LLM 配置（二选一）
# --- 方案 A: 使用 Kimi（推荐，国内可用）---
LLM=openai
OPENAI_API_KEY=your_kimi_api_key
OPENAI_MODEL=kimi-k2-thinking
OPENAI_API_URL=https://api.moonshot.cn/v1/chat/completions

# --- 方案 B: 使用 Gemini ---
# LLM=gemini
# GEMINI_API_KEY=your_gemini_api_key
```

> 完整配置项参考 `bot/.env.example`

### 3. Docker 部署

```bash
# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

### 4. 本地开发

```bash
cd bot
pip install -r requirements.txt
python main.py
```

---

## 配置信息源

### Twitter 源

Twitter 不提供公开 RSS，需要通过 RSS 服务转换：

1. 使用 [RSS.app](https://rss.app) 或自建 RSSHub 获取 Twitter RSS URL
2. 通过 Bot `/sources` 命令添加 RSS URL

### 网站 RSS 源

预置 8 个 Web3 媒体:

- Cointelegraph: `https://cointelegraph.com/rss`
- CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/`
- The Block Beats: `https://api.theblockbeats.news/v1/open-api/home-xml`
- TechFlow Post: `https://techflowpost.substack.com/feed`
- DeFi Rate: `https://defirate.com/feed`
- Prediction News: `https://predictionnews.com/rss/`
- Event Horizon: `https://nexteventhorizon.substack.com/feed`
- un.Block (吴说): `https://unblock256.substack.com/feed`

可通过 `/sources` 命令添加更多。

---

## 定时任务

| 时间（北京） | 任务 | 说明 |
|-------------|------|------|
| **每小时** | 预抓取 RSS | 解决 RSS.app 只返回最近 25 条的问题 |
| **每 30 分钟** | 检查到期用户 | Free 用户 24h 周期，Pro 用户可自定义（v1.7.0） |
| **02:30/08:30/14:30/20:30** | 用户画像更新 | 基于反馈批量更新 |
| **00:30** | 数据清理 | 删除过期文件 + 清理缓存 |

> **注**：v1.6.0 起采用按用户间隔推送策略。Free 用户 24 小时周期，Pro 用户可自定义（最短 1 小时）。静默时段（00:00-07:00）不推送。

---

## 使用指南

### 新用户注册流程

1. 发送 `/start` 进入主菜单
2. 点击「开始设置」进入 3 轮 AI 对话：
   - **Round 1**：询问区块链生态系统偏好（Ethereum/Solana/Layer2）
   - **Round 2**：询问内容类型偏好（DeFi/NFT/交易/开发）
   - **Round 3**：生成画像摘要，用户确认
3. 配置信息源（自定义/使用默认）
4. 等待首份简报（约 24 小时后自动推送）

### 信息源管理

#### 添加 Twitter 源
1. 进入「信息源管理」→「Twitter」
2. 输入 Twitter List RSS URL（从 RSS.app 或 RSSHub 获取）
3. 系统验证后自动添加

#### 添加网站 RSS
1. 进入「信息源管理」→「网站」
2. 输入网站域名或完整 RSS URL
3. 系统自动检测 RSS 地址（支持多种路径）

### AI 对话

直接向 Bot 发送消息即可开始对话，AI 会：
- 读取你的用户画像
- 调用 Google Search 获取实时信息（Gemini）
- 参考最近 3 天推送内容回答问题

**示例**：
- "最近 Ethereum Layer2 有什么重大更新？"
- "帮我总结昨天简报中的 DeFi 协议动态"
- "解释一下 EIP-4844 的技术细节"

---

## 测试

```bash
cd bot
python -m pytest tests/ -v
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [产品需求文档](./产品需求文档_PRD_Final.md) | 产品定位、功能设计 |
| [测试用例](./测试用例与验收标准_Test_Cases.md) | 测试用例、验收标准 |

---

## 多语言支持

Bot 自动检测用户语言并翻译简报内容，支持：
- 中文（zh）
- 英语（en）
- 日语（ja）
- 韩语（ko）
- 俄语（ru）
- 西班牙语（es）
- 法语（fr）
- 德语（de）

---

## 核心数据流

```
用户注册 → AI 对话收集偏好 → 配置信息源
                                    ↓
                            【每小时】预抓取 + 去重缓存
                                    ↓
                            【每30分钟】检查到期用户，从缓存读取（500-1000条）
                                    ↓
                    Step 1: 两阶段 AI 筛选
                            ├─ Stage 1: 分批粗筛（每批100条 → 10-15条）
                            └─ Stage 2: 精选去重（候选池 → 25条）
                                    ↓
                    Step 2: 语言适配（独立翻译步骤）
                                    ↓
                    Telegram 推送（分条发送）
                                    ↓
    用户反馈（👍/不感兴趣）→ 定期更新画像 ──┘
```

---

## MVP 目标

| 指标 | 目标 |
|------|------|
| 支持用户数 | 100 人 |
| 信息源 | Twitter + 网站 RSS |
| 推送渠道 | Telegram |
| 推送频率 | 每日 1 次 |
| 筛选率 | 85-95%（200+ 条 → 15-30 条）|

---

## 扩展性

### 数据库升级
JSON 文件适合 MVP（100 用户），规模扩展可迁移至：
- PostgreSQL（结构化数据）
- MongoDB（用户画像）
- Redis（缓存 + 实时数据）

### 功能扩展
- 多平台推送（Discord/Slack/Email）
- 实时推送（突发事件）
- 社区功能（用户间分享）
- 数据分析（行业趋势报告）

---

## 开发指南

### 查看日志
```bash
# 本地运行
tail -f data/logs/bot.log

# Docker 运行
docker-compose logs -f
```

### 手动触发推送（仅管理员）
```bash
# 在 Telegram 中向 Bot 发送（需管理员权限）
/test
```

### 调试模式
修改 `main.py` 中的日志级别：
```python
logger.setLevel(logging.DEBUG)
```

---

## 贡献

欢迎提交 Issue 和 Pull Request！

## License

MIT

---

**问题反馈**: 请提交 [Issue](https://github.com/your-repo/info_denoise_compress/issues)
