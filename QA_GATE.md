# 测试门禁清单（QA Gate）

> 目标：没有测试证据，不允许合并与发布。

## 1. 门禁原则

- 每个需求必须先定义“可验证标准”
- 每次改动至少覆盖：
  - 功能测试
  - 关键回归测试
  - 盲区/异常对抗测试
- 必须保留测试证据（命令与结果摘要）

## 2. 提测前自检

- 代码范围仅包含本任务相关改动
- 无明显临时文件、调试残留
- 本地可运行、无基础语法错误

## 3. 必跑测试（按任务选择）

## 3.1 通知与启动相关

- `pytest -q bot/tests/test_auto_changelog_notify.py`
- `pytest -q bot/tests/test_changelog_script_idempotent.py`

验收重点：

- 启动时版本检测正常
- 同版本通知会跳过（幂等）
- 发送部分失败不写版本标记

## 3.2 群简报相关

- `pytest -q bot/tests/test_group_digest_generation.py`
- `pytest -q bot/tests/test_group_setup_and_cta.py`

验收重点：

- 群简报走真实 AI 生成链路
- 消息含可点击原文链接
- 超长内容分段发送

## 4. 线上验证门禁

部署后必须补充：

1. 服务状态：`sudo docker compose ps bot`
2. 日志关键字验证（与本次功能对应）
3. 1 条真实业务链路手工验证

## 5. 提交/PR 模板（最小）

- 功能点：
- 测试命令：
- 测试结果：
- 证据摘录（关键日志或输出）：

示例：

- 功能点：changelog 通知幂等防重
- 测试命令：`pytest -q bot/tests/test_changelog_script_idempotent.py`
- 测试结果：`3 passed in 0.39s`
- 证据：`Skip notification: latest version ... already notified`

