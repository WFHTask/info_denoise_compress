# 发布与回滚标准流程（SOP）

> 目标：把“开发 -> 测试 -> 合并 -> 部署 -> 验证 -> 回滚”固定为一套可重复执行流程。

## 1. 适用范围

- 分支基线：`beta1.0`
- 正式仓库：`/home/ubuntu/github-projects/info_denoise_compress`
- 开发仓库：`/home/ubuntu/github-projects/info_denoise_compress_dev`
- 当前变更策略：CHANGELOG 通知仅保留本地 `post-merge` 触发，不依赖 GitHub Actions

## 2. 开发阶段（Dev）

1. 同步基线分支
   - `git fetch origin && git checkout beta1.0 && git pull`
2. 新建任务分支
   - `git checkout -b feature/<name>` 或 `fix/<name>`
3. 完成开发与本地测试（见 `QA_GATE.md`）
4. 提交 PR 到 `beta1.0`

## 3. 合并阶段（PR）

1. PR 标题要说明“问题类型 + 目标”
2. PR 描述必须包含：
   - 问题是什么
   - 改了什么
   - 为什么这样改
   - 测试证据（命令+结果）
3. 合并顺序建议：
   - 先 `fix/*`，再 `feature/*`

## 4. 部署阶段（Prod）

在正式仓库执行：

1. 同步代码
   - `git checkout beta1.0 && git fetch origin && git merge --no-edit origin/beta1.0`
2. 重启服务（先停后启，避免重复进程）
   - `sudo docker compose stop bot`
   - `sudo docker compose up -d bot`
3. 检查服务状态
   - `sudo docker compose ps bot`

## 5. 发布后验证（必须）

至少完成以下 3 条：

1. **服务健康**：容器为 `Up` 状态
2. **关键日志**：本次改动相关日志出现且无报错
3. **业务链路**：手动触发 1 条关键流程确认可用

## 6. 回滚流程（最小可用）

当新版本出现严重故障：

1. 先恢复服务可用性
   - 回到上一个稳定 commit（建议使用已记录的稳定点）
2. 重启服务
   - `sudo docker compose stop bot && sudo docker compose up -d bot`
3. 验证核心链路恢复
4. 记录事故复盘（原因、影响、修复、预防）

## 7. 变更记录要求

每次发布必须在 CHANGELOG 记录：

- 解决的问题
- 具体变更
- 带来的收益

