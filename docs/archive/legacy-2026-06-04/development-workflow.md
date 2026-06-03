# GitHub 协作流程

本文档合并原 Git 指南、Issue 规则和协作约定，保持项目现有 GitHub Issues、Labels、Milestone、Project Board、分支和 PR 命名逻辑一致。

## 基本原则

- 使用 GitHub 管理需求、任务、缺陷和文档工作。
- 每个清晰任务对应一个 Issue。
- 一个 Issue 对应一个独立分支。
- 不直接向 `main` 推送代码。
- 通过 Pull Request 合并到 `main`。
- PR 描述应说明关联 Issue、修改内容、测试方式和影响范围。
- 文档任务和业务代码任务尽量分开。

## 标准流程

```text
确认 Issue
→ 同步 main
→ 创建任务分支
→ 修改相关文件
→ 本地检查
→ Commit
→ Push
→ 创建 Pull Request
→ Review
→ 合并到 main
```

## Windows PowerShell 命令

```powershell
git checkout main
git pull origin main

git checkout -b feat/us-04-02-create-activity-form

git status
git add app/routes/activity.py app/templates/activity_create.html
git commit -m "feat(US-04-02): add activity creation validation"
git push --set-upstream origin feat/us-04-02-create-activity-form
```

## 通用命令

```bash
git checkout main
git pull origin main

git checkout -b feat/us-04-02-create-activity-form

git status
git add app/routes/activity.py app/templates/activity_create.html
git commit -m "feat(US-04-02): add activity creation validation"
git push --set-upstream origin feat/us-04-02-create-activity-form
```

## Issue 命名

推荐格式：

```text
[US-01-01] Visitor can browse activity cards on the homepage
[TASK-02] Design core database models
[BUG-01] Fix login error message display
[DOC-04] Improve final README documentation
[UI-01] Define consistent Gatherly page style
```

常用编号：

| 前缀 | 含义 |
| --- | --- |
| `US` | 用户故事 |
| `TASK` | 技术任务或项目任务 |
| `BUG` | 缺陷修复 |
| `DOC` | 文档任务 |
| `UI` | 页面或样式任务 |

## Labels

项目中可继续使用以下类型和模块标签：

| Label | 含义 |
| --- | --- |
| `type: user story` | 用户视角功能需求 |
| `type: task` | 技术或实现任务 |
| `type: bug` | 缺陷修复 |
| `type: docs` | 文档任务 |
| `type: enhancement` | 优化或增强 |
| `module: activity` | 活动模块 |
| `module: auth` | 认证模块 |
| `module: circle` | 同好圈模块 |
| `module: frontend` | 模板、CSS、JS、页面展示 |
| `module: backend` | Flask 路由、表单、模型或业务逻辑 |
| `module: trust` | 评分、互评、信任分 |
| `module: docs` | 文档 |

如果仓库现有 Label 名称略有差异，应以 GitHub 当前设置为准，不在文档中单独发明另一套标签体系。

## Milestone

推荐继续使用以下阶段：

| Milestone | 范围 |
| --- | --- |
| `Sprint 1 - Basic Framework` | 基础框架、核心页面雏形、基础文档 |
| `Sprint 2 - Core Features` | 活动、报名、同好圈、信任机制等核心闭环 |
| `Final Delivery - Gatherly Release` | 最终文档、截图、测试、演示和答辩材料 |

## Project Board 状态

| 状态 | 含义 |
| --- | --- |
| Product Backlog | 后续可能做，但不一定在当前 Sprint |
| Sprint Backlog | 当前 Sprint 计划完成 |
| In Progress | 正在开发或整理 |
| Code Review | 已提交 PR，等待审查 |
| Done | 已完成并合并，或已确认关闭 |

## 分支命名

每个 Issue 使用一个分支。

推荐：

```text
feat/us-01-01-homepage-cards
feat/us-02-01-register
feat/us-04-02-create-activity-form
fix/bug-01-login-message
docs/doc-04-readme
ui/ui-01-style-guide
task/task-02-database-models
```

当前文档整理分支：

```text
docs/reorganize-docs-readme-er
```

## Commit 命名

推荐使用简洁、可追踪的提交信息：

```text
feat(US-01-01): add homepage activity cards
feat(US-05-03): prevent duplicate activity registration
fix(BUG-01): correct login flash message
docs(DOC-04): update final README
style(UI-01): unify activity card layout
```

## Pull Request 描述模板

```markdown
## Related Issue

Closes #XX

## Summary

- 
- 

## Test Plan

- [ ] Ran `python -m compileall app run.py`
- [ ] Ran `python run.py`
- [ ] Checked related pages manually
- [ ] Confirmed no unrelated files or secrets are included

## Screenshots

Add screenshots for visible UI changes.

## Review Focus

- 
```

## 合并前检查

- 分支来自最新 `main`。
- 只解决当前 Issue 或明确相关的一组小任务。
- 没有提交 `.env`、数据库文件、虚拟环境、缓存或真实上传文件。
- 至少执行 `python -m compileall app run.py`。
- 页面改动已本地打开检查。
- UI 改动已补充截图。
- PR 关联 Issue。
- Project Board 状态已更新。

