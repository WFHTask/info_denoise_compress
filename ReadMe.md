# Web3 Daily Digest

> 🚀 AI 驱动的 Web3 个性化信息聚合服务

每天帮你从海量信息中筛选出真正有价值的内容，10 分钟看完，不错过任何重要信息。

## ✨ 核心特点

- **AI 个性化筛选** - 基于用户画像，LLM 语义理解，不是关键词匹配
- **对话式偏好设置** - 3 轮 AI 对话完成偏好收集，无需填表
- **价值可感知** - 每份简报展示"扫描了多少、精选了多少、节省了多少时间"
- **反馈学习闭环** - 用户反馈 → AI 学习 → 推送越来越准
- **More Intelligence, Less Structure** - 用户画像用自然语言描述，AI 自己决定如何使用

## 📦 功能概览

```
用户注册 → AI 对话收集偏好 → 每日自动抓取 → AI 智能筛选 → 生成简报 → Telegram 推送
                                    ↑                                         ↓
                                    └──────── AI 分析反馈，更新用户画像 ←──────┘
```

**MVP 范围**：
- ✅ Twitter + 网站信息源
- ✅ AI 个性化筛选与简报生成
- ✅ Telegram Bot 推送
- ✅ 用户反馈收集与学习闭环

## 🛠 技术栈

| 模块 | 选型 |
|------|------|
| 核心框架 | [WiseFlow](https://github.com/TeamWiseFlow/wiseflow) - LLM 驱动的信息抓取 |
| 推送能力 | 借鉴 [TrendRadar](https://github.com/zhu327/TrendRadar) |
| Twitter 信源 | RSS.app（Twitter → RSS） |
| AI 服务 | 硅基流动 / DeepSeek（OpenAI 兼容 API） |
| 数据存储 | JSON 文件（MVP 轻量方案） |
| 部署 | Docker |

## 📁 项目结构

```
.
├── README.md                           # 本文件
├── 【定稿】产品需求文档_PRD_Final.md      # 产品需求文档
├── 技术路线文档_Technical_Roadmap.md     # 技术方案详细说明
├── 测试用例与验收标准_Test_Cases.md      # 测试与验收文档
├── Bot/                                # 开发代码（待开发）
├── WiseFlow/                           # WiseFlow 核心框架
└── TrendRadar/                         # TrendRadar 参考代码
```

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/web3-daily-digest.git
cd web3-daily-digest

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key、Telegram Bot Token 等

# 3. 启动服务
docker-compose up -d
```

详细部署说明请参考 [技术路线文档](./技术路线文档_Technical_Roadmap.md)。

## 📖 文档索引

| 文档 | 说明 |
|------|------|
| [产品需求文档](./【定稿】产品需求文档_PRD_Final.md) | 产品定位、功能设计、商业模式 |
| [技术路线文档](./技术路线文档_Technical_Roadmap.md) | 技术选型、架构设计、Prompt 设计 |
| [测试与验收](./测试用例与验收标准_Test_Cases.md) | 测试用例、验收标准 |

## 🎯 MVP 目标

| 指标 | 目标 |
|------|------|
| 支持用户数 | 100 人 |
| 信息源 | Twitter + 网站 |
| 推送渠道 | Telegram |
| 推送频率 | 每日 1 次 |

## 📄 License

MIT

---

**问题反馈**：请提交 Issue 或联系项目负责人
