# Web3 信息智能聚合方案选型报告

> 文档版本：v1.0  
> 更新日期：2025年1月

---

## 1. 背景与目标

### 1.1 业务背景

VoiVerse 定位为"AI Agent 分发入口"，需要为用户提供高质量的 Web3 资讯服务。Web3 领域信息具有以下特点：

- **碎片化严重**：信息分散在数十个媒体平台
- **24/7 全天候产出**：加密市场不休市，信息持续产生
- **信噪比极低**：大量空投广告、带货推广、重复转载

### 1.2 核心需求

构建一套自动化系统，实现：

1. **信息采集**：从指定 Web3 媒体源抓取内容
2. **智能降噪**：过滤垃圾信息，提取核心信号
3. **压缩推送**：每日生成简报，通过微信/Telegram 推送

### 1.3 待接入信息源

| 信息源 | 类型 | 语言 |
|-------|------|------|
| Cointelegraph | 全球头部新闻 | 英文 |
| ME News | 实时资讯 | 中文 |
| ChainCatcher | 核心媒体 | 中文 |
| TechFlow 深潮 | 深度分析 | 中文 |

---

## 2. 候选方案对比

### 2.1 方案概览

| 维度 | WiseFlow | TrendRadar | nbot.ai |
|------|----------|------------|---------|
| 项目地址 | [GitHub](https://github.com/TeamWiseFlow/wiseflow) | [GitHub](https://github.com/sansan0/TrendRadar) | [官网](https://nbot.ai/) |
| 开源协议 | Apache 2.0 | MIT | 闭源 SaaS |
| 技术架构 | Python + LLM | Python + MCP | 云服务 |
| 部署方式 | Docker/本地 | Docker/本地/GitHub Actions | 无需部署 |
| 数据源支持 | 网页抓取 | 35+ 热榜平台 + RSS + 自定义爬虫 | 预设源 |
| 推送渠道 | 自定义 | 微信/飞书/钉钉/Telegram/邮件 | 社区分享 |

### 2.2 WiseFlow 分析

**优点：**
- 侧重智能监控和追踪
- 支持自定义关注点配置
- 使用 LLM 进行内容理解

**缺点：**
- 需要自行实现推送渠道
- 对 Web3 特定源支持有限
- 配置相对复杂，学习曲线较陡

**适用场景：** 需要深度定制、有较强开发能力的团队

### 2.3 TrendRadar 分析

**优点：**
- 原生支持 35+ 热榜平台
- 内置企业微信/Telegram 推送
- 支持 RSS 订阅 + 自定义爬虫扩展
- MCP 架构支持 AI 分析
- 配置简单，开箱即用
- 支持关键词过滤和必选词机制
- 活跃维护，文档完善

**缺点：**
- 默认不支持需要 JS 渲染的网站
- 部分高级功能需要配置 AI API

**适用场景：** 快速搭建多源聚合推送系统

### 2.4 nbot.ai 分析

**优点：**
- 无需部署，即开即用
- 自然语言描述需求
- 内置内容过滤功能

**缺点：**
- 闭源 SaaS，数据不可控
- 信息源受限于平台预设
- 无法深度定制降噪规则
- 长期成本不可控
- 依赖第三方服务稳定性

**适用场景：** 快速验证、对数据隐私要求不高的场景

---

## 3. 选型决策

### 3.1 最终选择：TrendRadar

基于以下考量，选择 **TrendRadar** 作为实施方案：

### 3.2 决策理由

#### ✅ 理由一：多平台支持，扩展性强

TrendRadar 原生支持 35+ 热榜平台，同时支持：
- RSS 订阅（Cointelegraph、TechFlow 可直接接入）
- 自定义爬虫扩展（ChainCatcher、ME News 可开发专用爬虫）

```yaml
# 示例：RSS 信息源配置
rss:
  feeds:
    - id: "cointelegraph"
      name: "Cointelegraph"
      url: "https://cointelegraph.com/rss"
    - id: "techflow"
      name: "深潮 TechFlow"
      url: "https://techflowpost.substack.com/feed"
```

#### ✅ 理由二：内置降噪机制

支持关键词黑白名单，完美匹配"降噪"需求：

```yaml
# 噪音过滤配置
noise_filter:
  blacklist_keywords:  # 过滤
    - "空投"
    - "airdrop"
    - "免费领取"
  whitelist_keywords:  # 保留
    - "融资"
    - "安全漏洞"
    - "协议升级"
```

#### ✅ 理由三：原生微信推送支持

开箱即用的企业微信 Webhook 推送，无需额外开发：

```yaml
notification:
  channels:
    wework:
      webhook_url: "https://qyapi.weixin.qq.com/..."
      msg_type: "markdown"
```

#### ✅ 理由四：轻量部署

- 支持本地 Python 直接运行
- 支持 Docker 容器化部署
- 支持 GitHub Actions 定时触发
- 资源占用低，适合长期运行

#### ✅ 理由五：开源可控

- MIT 开源协议，可自由修改
- 数据完全自主，无隐私风险
- 社区活跃，持续维护

### 3.3 方案对比总结

| 评估维度 | 权重 | WiseFlow | TrendRadar | nbot.ai |
|---------|------|----------|------------|---------|
| 多源支持 | 20% | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 降噪能力 | 25% | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 推送渠道 | 20% | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 部署难度 | 15% | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 可控性 | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| 维护成本 | 10% | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **综合得分** | 100% | **3.4** | **4.5** | **2.8** |

---

## 4. 实施概要

### 4.1 已完成工作

| 任务 | 状态 | 说明 |
|------|------|------|
| TrendRadar 部署 | ✅ | 克隆至 `src/backend/TrendRadar` |
| RSS 源配置 | ✅ | Cointelegraph、TechFlow 等 7 个源 |
| ChainCatcher 爬虫 | ✅ | 自定义 HTML 解析爬虫 |
| 降噪规则配置 | ✅ | 黑白名单关键词已配置 |
| 推送脚本 | ✅ | `run_web3_push.py` |

### 4.2 信息源接入状态

| 信息源 | 方式 | 状态 |
|-------|------|------|
| Cointelegraph | RSS | ✅ 已接入 |
| TechFlow 深潮 | RSS (Substack) | ✅ 已接入 |
| ChainCatcher | 自定义爬虫 | ✅ 已接入 |
| ME News | 自定义爬虫 | ⚠️ 需 JS 渲染，暂不可用 |

### 4.3 替代/补充信息源

为弥补 ME News 暂不可用，已接入以下国际 Web3 媒体：

- CoinDesk
- The Block
- Decrypt
- Bitcoin Magazine
- Blockworks

---

## 5. 结论

**TrendRadar** 是最适合本项目的方案，原因总结：

1. **开箱即用**：内置微信推送，无需额外开发
2. **扩展性强**：支持 RSS + 自定义爬虫，可覆盖所有目标信息源
3. **降噪完善**：关键词过滤机制完美匹配业务需求
4. **部署简单**：Python 直接运行或 Docker 部署
5. **开源可控**：MIT 协议，数据自主

建议后续持续关注 WiseFlow 的发展，其 LLM 深度理解能力在未来可作为增强方案。

---

## 附录

### A. 参考链接

- [TrendRadar GitHub](https://github.com/sansan0/TrendRadar)
- [WiseFlow GitHub](https://github.com/TeamWiseFlow/wiseflow)
- [nbot.ai 官网](https://nbot.ai/)

### B. 相关文档

- [设计文档](./develop/design.md)
- [需求文档](./develop/requirements.md)
- [任务清单](./develop/tasks.md)