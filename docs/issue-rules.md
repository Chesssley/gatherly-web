# Issue 管理规则

本文档定义 Gatherly Web 的 Issue 编号、Labels、Milestone 和 Project Status 规则，保证小组协作时任务分类一致。

## Issue 标题格式

```text
[类型] 简短说明
```

示例：

- `[USERSTORY] 用户可以浏览近期活动`
- `[TASK] 创建活动详情页基础结构`
- `[BUG] 修复移动端导航换行问题`
- `[DOC] 补充 Git 协作说明`
- `[ENHANCEMENT] 优化活动卡片 hover 效果`

## 类型分类

| 类型 | 使用场景 |
|---|---|
| User Story | 从用户视角描述目标和价值 |
| Task | 开发任务、技术任务、页面搭建、配置调整 |
| Bug | 缺陷修复，例如链接错误、样式错位、表单异常 |
| Documentation | README、会议记录、截图、协作说明等文档任务 |
| Enhancement | 体验优化、视觉优化、交互优化或非核心增强 |

标题中建议使用以下前缀：

- `[USERSTORY]`
- `[TASK]`
- `[BUG]`
- `[DOC]`
- `[ENHANCEMENT]`

## 编号规则

| 编号前缀 | 含义 | 示例 |
|---|---|---|
| `US-xx` | 用户故事 | `US-02 用户注册与登录` |
| `TASK-xx` | 技术或项目任务 | `TASK-04 项目清理与 docs 优化` |
| `BUG-xx` | 缺陷修复 | `BUG-01 修复登录跳转错误` |
| `DOC-xx` | 文档任务 | `DOC-02 整理会议记录` |
| `UI-xx` | 页面或样式任务 | `UI-01 制定统一样式规范` |

编号应与 `docs/product-backlog.md` 保持一致。

## Labels 规则

建议使用以下 Labels：

| Label | 含义 |
|---|---|
| `user-story` | 用户故事 |
| `task` | 开发或技术任务 |
| `bug` | 缺陷修复 |
| `documentation` | 文档任务 |
| `enhancement` | 优化增强 |
| `frontend` | 模板、CSS、JS 或页面展示 |
| `backend` | Flask 路由、表单、模型或业务逻辑 |
| `database` | 数据库模型、初始化或迁移 |
| `priority-p0` | 必须完成 |
| `priority-p1` | 重要功能 |
| `priority-p2` | 可选加分功能 |

## Milestone 规则

| Milestone | 范围 |
|---|---|
| `Sprint 1` | 项目基础结构、核心页面雏形、基础文档 |
| `Sprint 2` | 核心业务闭环、报名、发布、同好圈等 |
| `Final Delivery` | 演示、截图、测试、最终文档和答辩材料 |

每个 Issue 都应设置 Milestone。暂不确定的需求先放入 Product Backlog，再由组长或会议决定 Sprint。

## Project Status 规则

| 状态 | 含义 |
|---|---|
| Product Backlog | 后续可能要做，但当前 Sprint 不做 |
| Sprint Backlog | 当前 Sprint 计划完成 |
| In Progress | 正在开发或整理 |
| Code Review | 已提交 PR，等待审查 |
| Done | 已完成并合并或确认关闭 |

## Issue 内容模板

```markdown
## 背景

说明为什么需要这个 Issue。

## 任务范围

- 需要完成的内容 1
- 需要完成的内容 2

## 验收标准

- 可以验证的结果 1
- 可以验证的结果 2

## 备注

关联页面、路由、截图或参考资料。
```

## 维护要求

- 一个 Issue 只做一类清晰任务。
- PR 需要关联对应 Issue。
- 状态变更后同步 GitHub Project。
- 文档任务和代码任务不要混在同一个 Issue 中，除非文档是该代码任务的验收标准之一。
