# 📚 VoiVerse Web3 信息聚合系统 - 文档中心

> 本目录包含系统的所有技术文档、配置指南和开发资料。

---

## 📖 文档索引

### 快速开始

| 文档 | 说明 |
|-----|------|
| [选型报告](./selection-report.md) | 技术选型分析与决策过程 |
| [API 配置指南](./api-config-guide.md) | RSS 源、推送渠道、AI API 配置 |
| [部署视频录制指南](./deploy-video-guide.md) | 视频演示脚本与录制技巧 |

### 开发文档

| 文档 | 说明 |
|-----|------|
| [设计文档](./develop/design.md) | 系统架构、组件接口、数据模型 |
| [需求文档](./develop/requirements.md) | 功能需求与非功能需求 |
| [任务清单](./develop/tasks.md) | 开发任务拆分与进度 |
| [TODO](./develop/TODO.md) | 待办事项 |

### AI 与 Prompt

| 文档 | 说明 |
|-----|------|
| [Prompt 合集](./prompts.md) | 各场景 Prompt 模板 |
| [API 配置与 Prompt 调优](./api-config-guide.md#4-prompt-调优过程) | Prompt 演进历程与调优经验 |

### 规则配置

| 文档 | 说明 |
|-----|------|
| [降噪规则](./rules.md) | 关键词黑白名单、优先级配置 |

---

## 🗂️ 目录结构

```
docs/
├── README.md                 # 本文件 - 文档索引
├── selection-report.md       # 技术选型报告
├── api-config-guide.md       # API 配置与 Prompt 调优指南
├── deploy-video-guide.md     # 部署视频录制指南
├── prompts.md                # Prompt 合集
├── rules.md                  # 降噪规则配置
└── develop/                  # 开发文档
    ├── design.md             # 设计文档
    ├── requirements.md       # 需求文档
    ├── tasks.md              # 任务清单
    └── TODO.md               # 待办事项
```

---

## 📊 系统状态概览

### 数据源接入状态

| 类型 | 总数 | 正常 | 异常 |
|-----|------|------|------|
| RSS 源 | 15 | 14 | 1 |
| Web3 爬虫 | 2 | 1 | 1 |
| **总计** | **17** | **15** | **2** |

### 已接入 RSS 源

| 来源 | 状态 | 语言 |
|-----|------|------|
| Cointelegraph | ✅ | EN |
| CoinDesk | ✅ | EN |
| The Block | ✅ | EN |
| Decrypt | ✅ | EN |
| Bitcoin Magazine | ✅ | EN |
| Blockworks | ✅ | EN |
| 深潮 TechFlow | ✅ | CN |
| CryptoSlate | ✅ | EN |
| NewsBTC | ✅ | EN |
| CryptoPotato | ✅ | EN |
| BeInCrypto | ✅ | EN |
| U.Today | ✅ | EN |
| CoinGape | ✅ | EN |
| Bitcoinist | ⚠️ | EN |
| CoinPedia | ✅ | EN |

### 已接入 Web3 爬虫

| 来源 | 状态 | 说明 |
|-----|------|------|
| ChainCatcher 链捕手 | ✅ | HTML 解析 |
| ME News | ❌ | SSL 证书过期 |

---

## 🔧 常用命令

```bash
# 测试模式（不推送）
python run_web3_push.py --test

# 预览模式
python run_web3_push.py --dry-run

# 正式运行
python run_web3_push.py
```

---

## 📝 文档维护指南

### 添加新文档

1. 在对应目录创建 `.md` 文件
2. 更新本 README 的文档索引
3. 在相关文档中添加交叉引用

### 文档格式规范

- 使用 Markdown 格式
- 标题使用 `#` 层级
- 代码块标注语言
- 表格对齐
- 添加更新日期

### 更新记录

| 日期 | 变更内容 |
|-----|---------|
| 2026-01-10 | 添加部署视频录制指南、演示脚本 |
| 2026-01-10 | 创建文档索引，添加 API 配置指南 |
| 2026-01-08 | 初始化文档结构 |

---

## 🔗 相关链接

- **项目源码**: `src/backend/TrendRadar/`
- **配置文件**: `src/backend/TrendRadar/config/config.yaml`
- **输出目录**: `src/backend/TrendRadar/output/`

---

*如有问题或建议，欢迎提交 Issue！*