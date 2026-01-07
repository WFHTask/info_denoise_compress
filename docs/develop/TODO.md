# TrendRadar 项目待办计划

> 创建日期：2025-01-07  
> 状态：进行中

---

## 📊 当前完成度

| 交付物 | 状态 | 完成度 |
|-------|------|-------|
| 1. 选型报告 | ✅ 已完成 | 100% |
| 2. 部署视频 | ❌ 未开始 | 0% |
| 3. 运行演示 | ⏳ 进行中 | 50% |
| 4. 源代码/配置文件 | ✅ 基本完成 | 80% |

---

## 🔴 高优先级任务

### Task 1: 配置推送渠道 Webhook

**目标**：配置实际可用的推送渠道

**步骤**：

- [ ] 1.1 选择推送渠道（二选一或都配）
  - 选项 A: 企业微信
  - 选项 B: Telegram

- [ ] 1.2 企业微信配置（如选择）
  - [ ] 下载企业微信 App
  - [ ] 创建群聊，拉入接收信息的好友
  - [ ] 群聊 → 右上角「...」→「群机器人」→「添加机器人」
  - [ ] 复制 Webhook URL
  - [ ] 编辑 `src/backend/TrendRadar/config/config.yaml`
  - [ ] 找到 `notification.channels.wework.webhook_url`，填入 URL
  - [ ] 设置 `notification.enabled: true`

- [ ] 1.3 Telegram 配置（如选择）
  - [ ] 在 Telegram 搜索 @BotFather
  - [ ] 发送 /newbot 创建 Bot，获取 Bot Token
  - [ ] 将 Bot 拉入群聊或直接发消息
  - [ ] 访问 `https://api.telegram.org/bot<Token>/getUpdates` 获取 chat_id
  - [ ] 编辑 `src/backend/TrendRadar/config/config.yaml`
  - [ ] 填入 `notification.channels.telegram.bot_token`
  - [ ] 填入 `notification.channels.telegram.chat_id`
  - [ ] 设置 `notification.enabled: true`

**配置文件位置**：`src/backend/TrendRadar/config/config.yaml`

**预估时间**：15-30 分钟

---

### Task 2: 验证运行

**目标**：确保抓取和推送流程正常工作

**步骤**：

- [ ] 2.1 安装依赖
  ```bash
  cd src/backend/TrendRadar
  pip install -r requirements.txt
  ```

- [ ] 2.2 测试爬虫
  ```bash
  python test_web3_crawler.py
  ```
  - 预期结果：ChainCatcher 能抓到数据，ME News 失败（正常）

- [ ] 2.3 测试抓取（不推送）
  ```bash
  python run_web3_push.py --test
  ```
  - 预期结果：显示抓取到的新闻列表

- [ ] 2.4 预览推送内容
  ```bash
  python run_web3_push.py --dry-run
  ```
  - 预期结果：显示格式化的推送内容

- [ ] 2.5 正式推送测试
  ```bash
  python run_web3_push.py
  ```
  - 预期结果：手机收到推送消息

**预估时间**：15 分钟

---

### Task 3: 录制部署视频

**目标**：完成交付物 2 - 部署视频

**内容要求**：
- [ ] 3.1 展示项目目录结构
- [ ] 3.2 展示配置文件修改过程（Webhook 配置）
- [ ] 3.3 展示依赖安装过程
- [ ] 3.4 展示启动命令
- [ ] 3.5 展示日志输出

**录制工具建议**：OBS / Windows 自带录屏 / ScreenToGif

**预估时间**：10-15 分钟

---

### Task 4: 录制运行演示视频

**目标**：完成交付物 3 - 运行演示

**内容要求**：
- [ ] 4.1 展示运行 `run_web3_push.py` 的过程
- [ ] 4.2 展示终端输出（抓取日志）
- [ ] 4.3 展示手机端收到的推送消息
- [ ] 4.4 对比原始信息源网站，说明「降噪」效果
  - 原网站有大量空投/广告信息
  - 推送内容只保留核心资讯

**预估时间**：10-15 分钟

---

## 🟡 中优先级任务

### Task 5: 整理配置文件交付物

**目标**：完成交付物 4 - 配置文件整理

**步骤**：

- [ ] 5.1 创建 `configs/` 交付目录
- [ ] 5.2 复制配置文件模板（移除敏感信息）
  - `config.yaml.template`
  - `web3_sources.yaml`
  - `frequency_words.txt`
- [ ] 5.3 编写配置说明文档 `configs/README.md`

**预估时间**：15 分钟

---

### Task 6: 完善降噪 Prompt（可选增强）

**目标**：如果使用 AI API，配置降噪 Prompt

**步骤**：

- [ ] 6.1 确认是否接入 AI API（OpenAI/Claude 等）
- [ ] 6.2 编写降噪 Prompt 模板
- [ ] 6.3 配置 API Key（通过环境变量）
- [ ] 6.4 测试 AI 降噪效果

**当前状态**：使用关键词规则降噪，已可运行。AI 为增强功能。

**预估时间**：30 分钟（如需要）

---

## 🟢 低优先级任务（后续优化）

### Task 7: Docker 容器化部署

- [ ] 7.1 编写 Dockerfile
- [ ] 7.2 编写 docker-compose.yml
- [ ] 7.3 配置数据卷持久化
- [ ] 7.4 测试容器运行

### Task 8: 定时任务配置

- [ ] 8.1 配置定时抓取（每 30 分钟）
- [ ] 8.2 配置每日推送时间（如 09:00）
- [ ] 8.3 使用 cron 或 Windows 任务计划

### Task 9: ME News 替代方案

- [ ] 9.1 调研 Playwright/Selenium 方案
- [ ] 9.2 实现 JS 渲染爬虫
- [ ] 9.3 或寻找替代信息源

### Task 10: 数据库持久化

- [ ] 10.1 配置 SQLite 存储
- [ ] 10.2 实现内容去重
- [ ] 10.3 实现推送记录存储

---

## 📁 文件清单

### 已完成的文件

| 文件 | 路径 | 说明 |
|-----|------|------|
| 选型报告 | `docs/selection-report.md` | ✅ 已完成 |
| 设计文档 | `docs/develop/design.md` | ✅ 已完成 |
| 需求文档 | `docs/develop/requirements.md` | ✅ 已完成 |
| 任务清单 | `docs/develop/tasks.md` | ✅ 已完成 |
| 主配置文件 | `src/backend/TrendRadar/config/config.yaml` | ✅ 已完成 |
| Web3 源配置 | `src/backend/TrendRadar/config/web3_sources.yaml` | ✅ 已完成 |
| 推送脚本 | `src/backend/TrendRadar/run_web3_push.py` | ✅ 已完成 |
| 测试脚本 | `src/backend/TrendRadar/test_web3_crawler.py` | ✅ 已完成 |
| ChainCatcher 爬虫 | `src/backend/TrendRadar/trendradar/crawler/web3/chaincatcher.py` | ✅ 已完成 |

### 待创建的文件

| 文件 | 路径 | 任务 |
|-----|------|------|
| 配置模板 | `configs/config.yaml.template` | Task 5 |
| 配置说明 | `configs/README.md` | Task 5 |
| 部署视频 | `docs/deploy-video.mp4` | Task 3 |
| 演示视频 | `docs/demo-video.mp4` | Task 4 |

---

## ⏱️ 时间估算

| 任务 | 预估时间 |
|------|---------|
| Task 1: 配置 Webhook | 15-30 分钟 |
| Task 2: 验证运行 | 15 分钟 |
| Task 3: 录制部署视频 | 10-15 分钟 |
| Task 4: 录制演示视频 | 10-15 分钟 |
| Task 5: 整理配置文件 | 15 分钟 |
| **总计** | **约 1-1.5 小时** |

---

## 🚀 快速开始命令

```bash
# 进入项目目录
cd src/backend/TrendRadar

# 安装依赖
pip install -r requirements.txt

# 测试爬虫
python test_web3_crawler.py

# 预览推送内容
python run_web3_push.py --dry-run

# 正式推送（需先配置 webhook）
python run_web3_push.py
```

---

## 📝 备注

1. **ME News 暂不可用**：该网站需要 JavaScript 渲染，当前爬虫无法获取数据，已在配置中禁用。已通过其他 6 个国际 Web3 媒体源补充。

2. **降噪规则已配置**：`web3_sources.yaml` 中已配置黑名单（空投、广告等）和白名单（融资、安全等）关键词。

3. **选型报告已完成**：`docs/selection-report.md` 包含完整的方案对比分析。