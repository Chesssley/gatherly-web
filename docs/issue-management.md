# Issue 管理规范

最后更新时间：2026-06-04

本文统一 Gatherly Web 的 Issues、Labels、Milestones 和 Project Board 使用规则。

## Issue 类型

| 类型 | 使用场景 |
|---|---|
| User Story | 从用户视角描述产品能力 |
| Task | 技术任务、流程设计、配置或结构搭建 |
| Bug | 缺陷、异常数据、错误跳转、页面报错 |
| Documentation | README、docs、截图、测试报告、会议记录 |
| Enhancement | 已有功能的体验优化 |
| UI / Style | 页面视觉、布局、响应式、CSS 规范 |

## Issue 标题格式

```text
[US-XX-XX] 功能名称
[TASK-XX] 技术任务名称
[BUG-XX] 缺陷名称
[DOC-XX] 文档任务名称
[UI-XX] 样式任务名称
[ENH-XX] 优化任务名称
```

示例：

- `[US-04-01] 登录用户进入活动发布页面`
- `[TASK-03] 设计活动报名业务流程`
- `[BUG-02] 清理同好圈测试圈子和异常数据来源`
- `[DOC-04] 完善最终 README 文档`
- `[UI-01] 制定 Gatherly 页面统一样式规范`
- `[ENH-03] 优化全站消息提醒自动消失`

不要把标题写成没有编号的泛化描述。当前开放 Issue `#118 Add new log` 建议后续重新命名或关闭。

## Labels 规则

Labels 建议分成四类。

### 类型 Label

| Label | 含义 |
|---|---|
| `type: user-story` | 用户故事 |
| `type: task` | 技术任务 |
| `type: bug` | 缺陷 |
| `type: documentation` | 文档任务 |
| `type: enhancement` | 优化 |
| `type: ui-style` | 样式任务 |

### 模块 Label

| Label | 含义 |
|---|---|
| `module: activity` | 活动相关 |
| `module: auth` | 注册登录和账号 |
| `module: circle` | 同好圈 |
| `module: profile` | 个人主页 |
| `module: message` | 私信 |
| `module: notification` | 通知 |
| `module: admin` | 管理员后台 |
| `module: database` | 数据库模型或迁移 |
| `module: docs` | 文档 |
| `module: style` | 样式 |

### 优先级 Label

| Label | 含义 |
|---|---|
| `priority: P0` | 核心必需 |
| `priority: P1` | 重要 |
| `priority: P2` | 可选优化 |

### Sprint Label

| Label | 含义 |
|---|---|
| `sprint: 1` | Sprint 1 |
| `sprint: 2` | Sprint 2 |
| `sprint: final` | 最终交付 |

## Milestones

| Milestone | 范围 |
|---|---|
| `Sprint 1 - Basic Framework` | Flask 基础结构、核心页面雏形、基础文档 |
| `Sprint 2 - Core Features` | 活动发布报名、同好圈、评分、个人主页、后台等核心功能 |
| `Final Delivery` | README、docs、测试报告、截图、演示材料、课程报告 |

每个 Issue 都应设置 Milestone。暂不确定的需求先放 Product Backlog，再由会议决定是否进入当前 Sprint。

## Project Board 状态

| 状态 | 含义 |
|---|---|
| Product Backlog | 后续可能要做，但当前 Sprint 不做 |
| Sprint Backlog | 当前 Sprint 计划完成 |
| In Progress | 正在开发或整理 |
| Code Review | 已提交 PR，等待检查 |
| Done | 已完成并合并或确认关闭 |

## Issue 内容模板

```markdown
## 背景

说明为什么需要这个 Issue。

## 任务范围

- 需要完成的内容 1
- 需要完成的内容 2

## 验收标准

- [ ] 可以验证的结果 1
- [ ] 可以验证的结果 2

## 建议修改文件

- app/routes/...
- app/templates/...
- docs/...

## 禁止修改 / 注意事项

- 不要引入 React、Vue、Bootstrap 或新依赖。
- 不要修改无关文件。

## 分支命名建议

feat/us-xx-xx-short-name

## Commit 示例

feat(US-XX-XX): short description
```

## 维护要求

- 不要乱改 Issue 数字编号。
- 不要复用已经关闭 Issue 的编号表达新需求。
- 不要把多个模块塞进一个 Issue。
- Bug Issue 要写清楚复现步骤、预期结果和实际结果。
- Documentation Issue 要写清楚需要更新的文档和截图路径。
- PR 要关联对应 Issue，例如 `Closes #55` 或 `Related to #85`。
- Project Board 状态变更后，同步更新 [product-backlog.md](product-backlog.md)。
