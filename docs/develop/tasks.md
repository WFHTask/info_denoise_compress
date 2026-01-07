# Implementation Plan

- [ ] 1. 项目初始化与基础架构
  - [-] 1.1 克隆 TrendRadar 仓库并配置开发环境



    - 克隆 https://github.com/sansan0/TrendRadar
    - 安装 Python 依赖 (requirements.txt)
    - 配置 Docker 环境
    - _Requirements: 1.1_
  - [ ] 1.2 创建项目目录结构和核心接口
    - 创建 crawlers/, filters/, push/, models/, utils/ 目录
    - 定义基础接口类和数据模型
    - _Requirements: 1.1_
  - [ ] 1.3 配置 SQLite 数据库和 ORM
    - 创建数据库 schema (articles, subscribers, push_logs, system_logs)
    - 实现数据库连接和基础 CRUD 操作
    - _Requirements: 1.1, 2.1_

- [ ] 2. 数据模型实现
  - [ ] 2.1 实现核心数据模型类
    - 实现 RawArticle, Article, DailySummary 数据类
    - 实现 Subscriber, UserPreferences 数据类
    - 实现 FilterConfig, PushResult 数据类
    - _Requirements: 2.1, 4.1_
  - [ ]* 2.2 编写数据模型属性测试
    - **Property 1: 内容去重幂等性** - 测试 content_hash 唯一性
    - **Validates: Requirements 2.4**

- [ ] 3. Web3 信息源爬虫实现
  - [ ] 3.1 实现爬虫基类 BaseCrawler
    - 实现 HTTP 请求、重试机制、错误处理
    - 实现 HTML 解析基础方法
    - _Requirements: 2.2, 2.3_
  - [ ] 3.2 实现 Cointelegraph 爬虫
    - 解析 https://cointelegraph.com/category/latest-news 页面结构
    - 提取标题、链接、发布时间、内容摘要
    - _Requirements: 2.2_
  - [ ] 3.3 实现 ME News 爬虫
    - 解析 https://www.me.news/news 页面结构
    - 提取标题、链接、发布时间、内容摘要
    - _Requirements: 2.2_
  - [ ] 3.4 实现 ChainCatcher 爬虫
    - 解析 https://www.chaincatcher.com/news 页面结构
    - 提取标题、链接、发布时间、内容摘要
    - _Requirements: 2.2_
  - [ ] 3.5 实现 TechFlow 深潮爬虫
    - 解析 https://www.techflowpost.com/zh-CN/newsletter 页面结构
    - 提取标题、链接、发布时间、内容摘要
    - _Requirements: 2.2_
  - [ ]* 3.6 编写爬虫单元测试
    - 使用 mock HTML 测试解析逻辑
    - 测试错误处理和重试机制
    - _Requirements: 2.2, 2.3_

- [ ] 4. 内容去重模块
  - [ ] 4.1 实现内容哈希计算和去重逻辑
    - 基于标题+URL 计算 content_hash
    - 实现数据库级别去重检查
    - _Requirements: 2.4_
  - [ ]* 4.2 编写去重属性测试
    - **Property 1: 内容去重幂等性** - 多次去重结果一致
    - **Validates: Requirements 2.4**

- [ ] 5. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. AI 降噪引擎实现
  - [ ] 6.1 实现关键词过滤规则引擎
    - 配置噪音关键词列表 (空投、白名单、免费领取等)
    - 配置信号关键词列表 (融资、漏洞、升级、安全等)
    - 实现关键词匹配和评分逻辑
    - _Requirements: 3.1, 3.2, 3.3_
  - [ ] 6.2 实现文章分类器
    - 实现 ArticleCategory 分类逻辑 (协议更新/投融资/安全事件/市场/其他)
    - 计算 signal_score 信号强度
    - _Requirements: 3.3_
  - [ ]* 6.3 编写降噪引擎属性测试
    - **Property 2: 噪音关键词过滤完整性** - 噪音内容被过滤
    - **Property 3: 信号关键词保留完整性** - 信号内容被保留
    - **Validates: Requirements 3.2, 3.3**

- [ ] 7. 摘要生成器实现
  - [ ] 7.1 实现每日简报生成逻辑
    - 聚合当日文章，按分类统计
    - 生成结构化摘要格式
    - _Requirements: 5.2_
  - [ ] 7.2 实现消息分段逻辑
    - 检测内容长度，超过 2048 字符时分段
    - 保证分段后信息完整性
    - _Requirements: 5.3_
  - [ ]* 7.3 编写摘要生成属性测试
    - **Property 6: 简报格式完整性** - 必填字段不为空
    - **Property 7: 消息分段正确性** - 分段不超过限制
    - **Validates: Requirements 5.2, 5.3**

- [ ] 8. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. 用户订阅管理实现
  - [ ] 9.1 实现订阅/取消订阅逻辑
    - 实现 subscribe(), unsubscribe() 方法
    - 实现状态持久化到数据库
    - _Requirements: 4.1, 4.2_
  - [ ] 9.2 实现用户偏好管理
    - 实现 set_preferences(), get_preferences() 方法
    - 实现偏好关键词筛选逻辑
    - _Requirements: 4.3, 4.4_
  - [ ]* 9.3 编写订阅管理属性测试
    - **Property 4: 订阅状态一致性** - 订阅/取消状态正确
    - **Property 5: 用户偏好持久化** - 偏好保存后可正确读取
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [ ] 10. 企业微信推送模块实现
  - [ ] 10.1 实现 WeCom Webhook 推送
    - 配置 WEWORK_WEBHOOK_URL
    - 实现 send_text(), send_markdown() 方法
    - 实现推送结果记录
    - _Requirements: 5.1_
  - [ ] 10.2 实现推送调度逻辑
    - 获取所有活跃订阅用户
    - 根据用户偏好筛选内容
    - 执行批量推送
    - _Requirements: 5.1_
  - [ ]* 10.3 编写推送模块属性测试
    - **Property 8: 推送覆盖完整性** - 所有活跃用户收到推送
    - **Validates: Requirements 5.1**

- [ ] 11. 任务调度器实现
  - [ ] 11.1 实现定时任务调度
    - 配置采集任务间隔 (默认 30 分钟)
    - 配置每日推送时间 (默认 09:00)
    - 使用 APScheduler 实现调度
    - _Requirements: 1.2, 5.1_
  - [ ] 11.2 实现异常恢复机制
    - 实现进程守护和自动重启
    - 实现状态持久化和恢复
    - _Requirements: 1.3_

- [ ] 12. 系统监控与日志
  - [ ] 12.1 实现系统状态查询
    - 实现各模块运行状态检查
    - 实现最近执行时间记录
    - _Requirements: 6.1_
  - [ ] 12.2 实现日志记录和告警
    - 配置日志级别和格式
    - 实现错误告警通知
    - _Requirements: 6.2, 6.3_

- [ ] 13. 配置管理与部署
  - [ ] 13.1 创建配置文件模板
    - 创建 config.yaml 配置模板
    - 配置 API 密钥、Webhook URL、降噪规则
    - _Requirements: 1.4, 3.1_
  - [ ] 13.2 创建 Docker 部署配置
    - 编写 Dockerfile
    - 编写 docker-compose.yml
    - 配置数据卷持久化
    - _Requirements: 1.1, 1.2_
  - [ ] 13.3 编写部署文档
    - 编写安装和配置说明
    - 编写常见问题解答
    - _Requirements: 1.1_

- [ ] 14. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. 交付物准备
  - [ ] 15.1 编写选型报告
    - 对比 WiseFlow、TrendRadar、nbot.ai 三个方案
    - 说明选择 TrendRadar 的理由（多平台支持、MCP 架构、微信推送、轻量部署）
    - 分析 TrendRadar 对 Web3 降噪需求的适配性
    - 输出 docs/selection-report.md
    - _Requirements: 交付标准 1_
  - [ ] 15.2 整理配置文件和 Prompt
    - 整理 config.yaml 配置模板
    - 整理降噪规则 Prompt 文本
    - 整理 frequency_words.txt 关键词配置
    - 输出 configs/ 目录
    - _Requirements: 交付标准 4_
  - [ ] 15.3 编写部署和演示指南
    - 编写 Docker 部署步骤说明
    - 编写 API 配置说明（企业微信 Webhook）
    - 编写运行演示操作指南
    - 输出 docs/deployment-guide.md
    - _Requirements: 交付标准 2, 3_
