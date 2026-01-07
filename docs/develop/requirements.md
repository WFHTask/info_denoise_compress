# Requirements Document

## Introduction

本系统基于 TrendRadar 开源项目，构建一个 Web3 信息智能聚合与降噪推送系统。系统部署在本地电脑长期运行，通过微信渠道向订阅用户推送经过 AI 清洗和压缩的 Web3 资讯简报。核心目标是解决 Web3 领域信息碎片化、信噪比低的问题，为用户提供高质量的信息摘要服务。

## Glossary

- **TrendRadar**: 开源的多平台热点聚合框架，支持 35+ 平台数据采集和 AI 分析
- **信息降噪**: 通过 AI 过滤垃圾信息、广告、重复内容，仅保留有价值的核心信息
- **信息源**: 待采集的 Web3 媒体网站，包括 Cointelegraph、ME News、ChainCatcher、TechFlow 深潮
- **简报**: 经过 AI 压缩和摘要后的每日信息汇总
- **订阅用户**: 通过微信关注并接收推送的用户
- **MCP 架构**: Model Context Protocol，TrendRadar 使用的 AI 分析架构

## Requirements

### Requirement 1

**User Story:** 作为系统管理员，我希望能够配置和部署 TrendRadar 系统，以便系统能够在本地电脑上长期稳定运行。

#### Acceptance Criteria

1. WHEN 管理员执行部署脚本 THEN 系统 SHALL 完成所有依赖安装并启动核心服务
2. WHEN 系统启动完成 THEN 系统 SHALL 在后台持续运行并记录运行日志
3. WHEN 系统遇到异常退出 THEN 系统 SHALL 自动重启并恢复到上次运行状态
4. WHEN 管理员配置 API 密钥 THEN 系统 SHALL 验证密钥有效性并安全存储

### Requirement 2

**User Story:** 作为系统管理员，我希望能够配置 Web3 信息源，以便系统能够从指定的媒体网站采集数据。

#### Acceptance Criteria

1. WHEN 管理员添加新的信息源 URL THEN 系统 SHALL 验证 URL 可访问性并保存配置
2. WHEN 采集任务执行 THEN 系统 SHALL 从 Cointelegraph、ME News、ChainCatcher、TechFlow 深潮获取最新内容
3. WHEN 信息源返回错误 THEN 系统 SHALL 记录错误日志并在下次调度时重试
4. WHEN 采集到重复内容 THEN 系统 SHALL 基于内容哈希进行去重处理

### Requirement 3

**User Story:** 作为系统管理员，我希望能够配置 AI 降噪规则，以便系统能够过滤低质量信息并提取核心信号。

#### Acceptance Criteria

1. WHEN 管理员配置降噪规则 THEN 系统 SHALL 解析规则并应用到内容过滤流程
2. WHEN 内容包含空投广告关键词 THEN 系统 SHALL 将该内容标记为噪音并过滤
3. WHEN 内容涉及协议更新、投融资或安全事件 THEN 系统 SHALL 将该内容标记为核心信号并保留
4. WHEN AI 分析完成 THEN 系统 SHALL 生成结构化的内容摘要

### Requirement 4

**User Story:** 作为订阅用户，我希望能够通过微信订阅推送服务，以便我能够接收每日的 Web3 信息简报。

#### Acceptance Criteria

1. WHEN 用户发送订阅指令到微信公众号 THEN 系统 SHALL 记录用户订阅状态并返回确认消息
2. WHEN 用户发送取消订阅指令 THEN 系统 SHALL 更新用户状态并停止向该用户推送
3. WHEN 用户查询订阅状态 THEN 系统 SHALL 返回当前订阅状态和配置信息
4. WHEN 用户设置偏好关键词 THEN 系统 SHALL 保存偏好并在推送时进行个性化筛选

### Requirement 5

**User Story:** 作为订阅用户，我希望每天能够收到经过压缩和降噪的 Web3 信息简报，以便我能够快速了解行业动态。

#### Acceptance Criteria

1. WHEN 到达每日推送时间 THEN 系统 SHALL 向所有活跃订阅用户发送当日简报
2. WHEN 生成简报内容 THEN 系统 SHALL 将多条新闻压缩为结构化摘要格式
3. WHEN 简报内容超过微信消息长度限制 THEN 系统 SHALL 分段发送或提供详情链接
4. WHEN 当日无有效内容 THEN 系统 SHALL 发送无更新通知而非空消息
