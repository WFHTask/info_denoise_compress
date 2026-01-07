# Claude Code 使用规则

> 本文档用于约束 Claude Code 的行为，避免重复犯错。团队成员发现 Claude 犯错时，请添加规则。

---

## 代码风格

- Python 文件必须使用 UTF-8 编码
- 配置文件必须有中文注释
- 新增函数必须写 docstring
- 日志输出使用统一格式：`[模块名] 消息内容`

## 禁止行为

- 不要硬编码 API Key、Webhook URL、密码等敏感信息
- 不要删除用户没有明确要求删除的代码
- 不要猜测文件路径，必须先用 `find_path` 或 `grep` 查找
- 不要在没有确认的情况下覆盖用户的配置文件
- 不要运行会持续运行的命令（如 `npm run dev`、`python -m http.server`）
- 不要假设依赖已安装，需要时先检查或提醒用户安装

## 文件操作规则

- 编辑文件前必须先 `read_file` 了解当前内容
- 创建新文件前必须用 `list_directory` 确认目录存在
- 大文件返回 outline 时，使用 `start_line/end_line` 读取具体部分，不要重复请求整个文件
- 移动/重命名文件使用 `move_path`，不要用 `terminal` 的 `mv` 命令

## 回答规范

- 代码块必须使用 `路径#L行号` 格式，不能只写语言名
- 不确定时先问用户，不要猜测用户意图
- 报错时给出具体解决方案，不要只说"请检查"
- 完成任务后简要总结做了什么，方便用户确认

## 项目约定

- TrendRadar 代码在 `src/backend/TrendRadar` 目录
- 配置文件在 `config/` 子目录
- 所有 Web3 爬虫放在 `trendradar/crawler/web3/` 目录
- 文档放在 `docs/` 目录，开发文档放在 `docs/develop/`

## 测试规范

- 修改核心逻辑后要运行相关测试
- 测试脚本命名：`test_*.py`
- 测试输出使用 emoji 状态：✅ 成功 / ❌ 失败 / ⚠️ 警告

## Git 规范

- 不要自动执行 `git commit` 或 `git push`，除非用户明确要求
- 敏感文件必须加入 `.gitignore`

---

## 错误记录

| 日期 | 错误描述 | 规则 |
|------|---------|------|
| 2025-01 | 把项目进展追踪写到 rules.md | rules.md 是给 Claude 的行为规则，不是项目文档 |