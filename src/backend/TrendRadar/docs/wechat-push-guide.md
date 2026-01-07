# 📱 微信推送配置指南

本指南将帮助你配置 TrendRadar 的微信推送功能，让你的微信好友能够订阅并接收 Web3 资讯简报。

## 目录

- [推送方式概览](#推送方式概览)
- [方案一：企业微信群机器人（推荐）](#方案一企业微信群机器人推荐)
- [方案二：Telegram Bot](#方案二telegram-bot)
- [方案三：邮件订阅](#方案三邮件订阅)
- [配置推送时间](#配置推送时间)
- [测试推送](#测试推送)
- [常见问题](#常见问题)

---

## 推送方式概览

| 方式 | 适用场景 | 难度 | 推荐指数 |
|------|----------|------|----------|
| 企业微信群机器人 | 微信群推送 | ⭐ 简单 | ⭐⭐⭐⭐⭐ |
| Telegram Bot | 海外用户 | ⭐⭐ 中等 | ⭐⭐⭐⭐ |
| 邮件订阅 | 通用方式 | ⭐⭐ 中等 | ⭐⭐⭐ |

---

## 方案一：企业微信群机器人（推荐）

这是最简单且效果最好的方式，可以直接将资讯推送到微信群。

### 第一步：准备工作

1. **下载企业微信**
   - iOS: App Store 搜索「企业微信」
   - Android: 应用商店搜索「企业微信」

2. **注册/登录**
   - 如果没有企业，可以创建一个小型团队（免费）
   - 或者让朋友邀请你加入他们的企业

### 第二步：创建群聊

1. 打开企业微信
2. 点击右上角 `+` → `发起群聊`
3. 选择需要接收信息的好友
4. 创建群聊

> 💡 **提示**：企业微信和个人微信互通，群成员可以在个人微信中接收消息。

### 第三步：添加群机器人

1. 进入刚创建的群聊
2. 点击右上角 `...`
3. 选择 `群机器人`
4. 点击 `添加机器人`
5. 选择 `新创建一个机器人`
6. 输入机器人名称，如「Web3 资讯推送」
7. 点击 `添加`
8. **复制生成的 Webhook 地址**（非常重要！）

Webhook 地址格式如下：
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 第四步：配置 TrendRadar

编辑 `config/config.yaml` 文件：

```yaml
notification:
  enabled: true  # 启用推送

  channels:
    wework:
      webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的密钥"
      msg_type: "markdown"  # 使用 markdown 格式，信息更美观
```

### 第五步：运行系统

```bash
# 进入项目目录
cd TrendRadar

# 运行抓取和推送
python -m trendradar
```

### 推送效果预览

企业微信群中将收到类似这样的消息：

```
📊 Web3 资讯日报 | 2026-01-07

━━━━━━━━━━━━━━━━━━━

📰 今日热点

1. 贝莱德高管：比特币仍处早期阶段
2. 数据：1992 枚 BTC 从 Fidelity Custody 转出
3. Uber 前高管推出与比特币挂钩的储蓄代币

━━━━━━━━━━━━━━━━━━━

🔗 来源：ChainCatcher、Cointelegraph、TechFlow
```

---

## 方案二：Telegram Bot

如果你的好友更习惯使用 Telegram，可以配置 Telegram 推送。

### 第一步：创建 Bot

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot`
3. 按提示设置 Bot 名称和用户名
4. 获取 **Bot Token**（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 第二步：获取 Chat ID

1. 创建一个群组或频道
2. 将你的 Bot 添加到群组
3. 发送一条消息
4. 访问：`https://api.telegram.org/bot<你的Token>/getUpdates`
5. 找到 `chat.id` 字段

### 第三步：配置 TrendRadar

```yaml
notification:
  enabled: true

  channels:
    telegram:
      bot_token: "你的Bot Token"
      chat_id: "你的Chat ID"  # 群组ID通常是负数，如 -1001234567890
```

---

## 方案三：邮件订阅

通过邮件推送，好友只需提供邮箱地址即可订阅。

### 第一步：获取邮箱授权码

以 QQ 邮箱为例：
1. 登录 QQ 邮箱网页版
2. 设置 → 账户 → POP3/SMTP服务
3. 开启服务并获取授权码

### 第二步：配置 TrendRadar

```yaml
notification:
  enabled: true

  channels:
    email:
      from: "your_email@qq.com"           # 发件邮箱
      password: "你的授权码"               # 不是邮箱密码！
      to: "friend1@qq.com,friend2@163.com" # 收件人，多个用逗号分隔
      smtp_server: "smtp.qq.com"          # QQ邮箱的SMTP服务器
      smtp_port: "465"                    # SSL端口
```

### 常用邮箱 SMTP 配置

| 邮箱 | SMTP 服务器 | 端口 |
|------|-------------|------|
| QQ 邮箱 | smtp.qq.com | 465 |
| 163 邮箱 | smtp.163.com | 465 |
| Gmail | smtp.gmail.com | 587 |
| Outlook | smtp.office365.com | 587 |

---

## 配置推送时间

你可以设置每天固定时间推送，避免全天打扰：

```yaml
notification:
  enabled: true

  push_window:
    enabled: true       # 启用时间窗口
    start: "08:00"      # 开始时间（北京时间）
    end: "09:00"        # 结束时间
    once_per_day: true  # 每天只推送一次
```

### 推荐的推送时间

- **早报**：08:00 - 09:00（适合上班族通勤阅读）
- **午报**：12:00 - 13:00（午休时间）
- **晚报**：20:00 - 21:00（下班后）

---

## 测试推送

配置完成后，可以手动测试推送是否正常：

```bash
# 运行一次抓取和推送
python -m trendradar

# 或者使用测试脚本
python test_web3_crawler.py
```

如果配置正确，你应该能在对应渠道收到测试消息。

---

## 常见问题

### Q1: 企业微信机器人发送失败？

**检查清单：**
- [ ] Webhook URL 是否正确复制（包含完整的 key 参数）
- [ ] 机器人是否还在群内（被移除后 webhook 会失效）
- [ ] 网络是否能访问 `qyapi.weixin.qq.com`

### Q2: 消息格式显示异常？

尝试切换消息类型：
```yaml
wework:
  msg_type: "text"  # 改为纯文本格式
```

### Q3: 推送太频繁了怎么办？

配置推送时间窗口，限制每天只推送一次：
```yaml
push_window:
  enabled: true
  once_per_day: true
```

### Q4: 如何添加多个推送群？

使用分号分隔多个 webhook：
```yaml
wework:
  webhook_url: "webhook1;webhook2;webhook3"
```

### Q5: 个人微信能直接收到推送吗？

企业微信和个人微信互通，群成员可以在个人微信中接收群消息。但暂不支持直接推送到个人微信私聊。

---

## 安全提醒

⚠️ **请妥善保管你的 Webhook URL 和各种密钥！**

- 不要将包含密钥的配置文件提交到公开的 Git 仓库
- 建议使用环境变量存储敏感信息
- 定期检查推送日志，防止被滥用

---

## 需要帮助？

如果遇到问题，可以：
1. 查看 `output/` 目录下的日志文件
2. 在 GitHub Issues 中提问
3. 参考 TrendRadar 官方文档