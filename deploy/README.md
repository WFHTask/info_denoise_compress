# TrendRadar Web3 信息聚合系统 - 部署指南

> 版本：v1.0  
> 更新日期：2025年1月

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速开始](#2-快速开始)
3. [详细配置](#3-详细配置)
4. [运行方式](#4-运行方式)
5. [推送渠道配置](#5-推送渠道配置)
6. [定时任务配置](#6-定时任务配置)
7. [Docker 部署](#7-docker-部署)
8. [常见问题](#8-常见问题)

---

## 1. 环境要求

### 1.1 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10+、macOS 10.15+、Linux |
| Python | 3.10 或更高版本 |
| 内存 | 最低 512MB，建议 1GB+ |
| 网络 | 能访问目标信息源网站 |

### 1.2 检查 Python 版本

```bash
python --version
# 或
python3 --version
```

输出应为 `Python 3.10.x` 或更高。

---

## 2. 快速开始

### 2.1 克隆/下载项目

```bash
# 如果使用 Git
git clone <项目地址>
cd VoiVerseProject
```

### 2.2 进入 TrendRadar 目录

```bash
cd src/backend/TrendRadar
```

### 2.3 安装依赖

```bash
# 使用 pip
pip install -r requirements.txt

# 或使用国内镜像加速
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.4 验证安装

```bash
# 运行环境检查脚本
python ../../.py

# 或测试爬虫
python test_web3_crawler.py
```

### 2.5 测试运行

```bash
# 预览模式（不推送）
python run_web3_push.py --dry-run
```

---

## 3. 详细配置

### 3.1 配置文件位置

```
src/backend/TrendRadar/config/
├── config.yaml          # 主配置文件
├── web3_sources.yaml    # Web3 信息源配置
└── frequency_words.txt  # 关键词配置
```

### 3.2 主配置文件 (config.yaml)

#### 时区配置

```yaml
app:
  timezone: "Asia/Shanghai"  # 北京时间
```

#### RSS 信息源配置

```yaml
rss:
  enabled: true
  feeds:
    # Cointelegraph - 全球头部加密新闻
    - id: "cointelegraph"
      name: "Cointelegraph"
      url: "https://cointelegraph.com/rss"
      max_age_days: 3

    # TechFlow 深潮 - 中文深度加密媒体
    - id: "techflow"
      name: "深潮 TechFlow"
      url: "https://techflowpost.substack.com/feed"
      max_age_days: 7
```

#### Web3 爬虫配置

```yaml
web3:
  enabled: true
  request_interval: 3000  # 请求间隔（毫秒）
  timeout: 30             # 超时时间（秒）
  feeds:
    - id: "chaincatcher"
      name: "ChainCatcher 链捕手"
      url: "https://www.chaincatcher.com/news"
      crawler_type: "chaincatcher"
      enabled: true
```

### 3.3 降噪规则配置 (web3_sources.yaml)

#### 噪音关键词（会被过滤）

```yaml
noise_filter:
  blacklist_keywords:
    - "空投"
    - "airdrop"
    - "免费领取"
    - "白嫖"
    - "撸毛"
    - "限时优惠"
    - "注册送"
    - "暴富"
    - "财富密码"
```

#### 信号关键词（会被保留）

```yaml
  whitelist_keywords:
    # 协议更新
    - "升级"
    - "更新"
    - "发布"
    - "主网"
    # 投融资
    - "融资"
    - "投资"
    - "收购"
    # 安全事件
    - "漏洞"
    - "攻击"
    - "被盗"
    - "安全"
```

---

## 4. 运行方式

### 4.1 命令行参数

```bash
# 正常运行（抓取 + 推送）
python run_web3_push.py

# 测试模式（只抓取，不推送）
python run_web3_push.py --test

# 预览模式（显示将要推送的内容）
python run_web3_push.py --dry-run
```

### 4.2 输出示例

```
============================================================
  Web3 资讯抓取与推送系统
  时间: 2025-01-07 16:30:00
============================================================

[1/4] 加载配置...
[OK] 配置加载成功

[2/4] 抓取 RSS 信息源...
[OK] RSS 抓取完成: 45 条

[3/4] 抓取 Web3 信息源...
[OK] Web3 抓取完成: 12 条

[4/4] 生成推送报告...
[OK] 报告生成完成

[PUSH] 开始推送...
[OK] 企业微信推送成功
============================================================
  推送完成
============================================================
```

---

## 5. 推送渠道配置

### 5.1 企业微信配置（推荐）

#### 获取 Webhook URL

1. 下载并登录「企业微信」App
2. 创建群聊，拉入需要接收信息的好友
3. 点击群聊右上角「...」→「群机器人」→「添加机器人」
4. 创建自定义机器人，复制 Webhook URL

#### 配置 config.yaml

```yaml
notification:
  enabled: true  # 改为 true
  channels:
    wework:
      webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"
      msg_type: "markdown"
```

### 5.2 Telegram 配置

#### 获取 Bot Token 和 Chat ID

1. 在 Telegram 搜索 `@BotFather`
2. 发送 `/newbot`，按提示创建 Bot
3. 记录返回的 `Bot Token`
4. 将 Bot 拉入群聊或直接给 Bot 发一条消息
5. 访问 `https://api.telegram.org/bot<你的Token>/getUpdates`
6. 在返回的 JSON 中找到 `chat.id`

#### 配置 config.yaml

```yaml
notification:
  enabled: true  # 改为 true
  channels:
    telegram:
      bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
      chat_id: "-1001234567890"
```

### 5.3 其他推送渠道

TrendRadar 还支持：

- 飞书 (feishu)
- 钉钉 (dingtalk)
- Slack
- Email
- Bark (iOS)
- ntfy

详见 `config.yaml` 中的 `notification.channels` 部分。

---

## 6. 定时任务配置

### 6.1 Windows 任务计划

1. 打开「任务计划程序」
2. 创建基本任务
3. 设置触发器（如每天 09:00）
4. 操作：启动程序
   - 程序：`python`
   - 参数：`run_web3_push.py`
   - 起始于：`<项目路径>\src\backend\TrendRadar`

### 6.2 Linux/macOS Cron

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天 9:00 和 18:00 执行）
0 9,18 * * * cd /path/to/src/backend/TrendRadar && python run_web3_push.py >> /var/log/trendradar.log 2>&1
```

### 6.3 使用内置推送窗口

也可以在 config.yaml 中配置推送时间窗口：

```yaml
notification:
  push_window:
    enabled: true
    start: "09:00"
    end: "10:00"
    once_per_day: true  # 窗口内只推送一次
```

---

## 7. Docker 部署

### 7.1 使用 Docker Compose（推荐）

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  trendradar:
    build: ./src/backend/TrendRadar
    container_name: trendradar-web3
    restart: unless-stopped
    volumes:
      - ./src/backend/TrendRadar/config:/app/config
      - ./src/backend/TrendRadar/output:/app/output
    environment:
      - TZ=Asia/Shanghai
```

运行：

```bash
docker-compose up -d
```

### 7.2 直接使用 Docker

```bash
# 构建镜像
cd src/backend/TrendRadar
docker build -t trendradar-web3 .

# 运行容器
docker run -d \
  --name trendradar \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/output:/app/output \
  -e TZ=Asia/Shanghai \
  trendradar-web3
```

---

## 8. 常见问题

### Q1: 安装依赖时报错

**问题**：`pip install` 失败

**解决**：
```bash
# 升级 pip
python -m pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: 抓取不到数据

**问题**：RSS 或 Web3 爬虫返回空数据

**可能原因**：
1. 网络问题 - 检查是否能访问目标网站
2. 被网站限制 - 增加 `request_interval`
3. 网站结构变化 - 需要更新爬虫代码

**解决**：
```bash
# 测试单个爬虫
python test_web3_crawler.py

# 检查网络
curl https://cointelegraph.com/rss
```

### Q3: 企业微信推送失败

**问题**：推送返回错误

**检查**：
1. Webhook URL 是否正确
2. `notification.enabled` 是否为 `true`
3. 消息格式是否正确

**测试 Webhook**：
```bash
curl 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key' \
  -H 'Content-Type: application/json' \
  -d '{"msgtype": "text", "text": {"content": "测试消息"}}'
```

### Q4: ME News 抓取失败

**问题**：ME News 返回空数据

**原因**：该网站使用 JavaScript 渲染，当前爬虫不支持

**解决**：已在配置中禁用，使用其他信息源替代：
- CoinDesk
- The Block
- Decrypt
- Blockworks

### Q5: Windows 终端乱码

**问题**：输出中文显示乱码

**解决**：
```bash
# 设置终端编码
chcp 65001
```

或在 PowerShell 中运行。

### Q6: 如何添加新的信息源？

**RSS 源**：在 `config.yaml` 的 `rss.feeds` 中添加：

```yaml
- id: "new-source"
  name: "新信息源"
  url: "https://example.com/rss"
  max_age_days: 3
```

**自定义爬虫**：在 `trendradar/crawler/web3/` 目录下创建新的爬虫类。

---

## 附录

### A. 项目目录结构

```
VoiVerseProject/
├── docs/
│   ├── selection-report.md    # 选型报告
│   └── develop/
│       ├── TODO.md            # 待办计划
│       ├── design.md          # 设计文档
│       └── requirements.md    # 需求文档
├── deploy/
│   └── README.md              # 本文档
└── src/backend/TrendRadar/
    ├── config/
    │   ├── config.yaml        # 主配置
    │   └── web3_sources.yaml  # 降噪规则
    ├── trendradar/
    │   └── crawler/web3/      # Web3 爬虫
    ├── run_web3_push.py       # 主程序
    └── test_web3_crawler.py   # 测试脚本
```

### B. 相关文档

- [选型报告](../docs/selection-report.md)
- [设计文档](../docs/develop/design.md)
- [待办计划](../docs/develop/TODO.md)

### C. 技术支持

如遇问题，请检查：
1. 本文档的「常见问题」部分
2. TrendRadar 官方文档：https://github.com/sansan0/TrendRadar
3. 项目 Issues