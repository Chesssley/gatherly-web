# Gatherly Product Backlog

本文档用于维护 Gatherly Web 的 Product Backlog、Sprint Backlog 和后续候选任务。安装和运行步骤统一放在根目录 `README.md`，本文件只记录需求、任务优先级和当前状态。

## 优先级说明

| 优先级 | 含义 |
|---|---|
| P0 | 必须完成；缺少该能力时项目无法形成核心闭环 |
| P1 | 重要功能；能体现项目特色或改善主要体验 |
| P2 | 加分功能；时间允许时再做 |

## 故事点说明

| 故事点 | 难度说明 |
|---|---|
| 1 | 很小的文档、样式或配置调整 |
| 2 | 简单页面、流程说明或低风险改动 |
| 3 | 中等复杂度，涉及页面展示、数据结构或基础交互 |
| 5 | 较复杂，涉及表单、数据库、登录状态或业务规则 |
| 8 | 复杂，涉及多个模块联动，当前阶段暂不优先 |

## Product Backlog 总表

| 编号 | 类型 | 用户故事 / 任务 | 优先级 | 故事点 | Sprint | 当前状态 |
|---|---|---|---|---|---|---|
| TASK-01 | Task | 搭建 Flask 基础项目结构 | P0 | 3 | Sprint 1 | Done |
| TASK-02 | Task | 设计用户表、活动表、报名表、圈子表、帖子表、评分表 | P0 | 3 | Sprint 1 | In Progress |
| TASK-03 | Task | 设计活动报名业务流程 | P1 | 2 | Sprint 1 | In Progress |
| TASK-04 | Documentation | 清理项目冗余文件并优化 docs 文档结构 | P1 | 2 | Sprint 1 | In Progress |
| US-01 | User Story | 作为游客，我想浏览首页活动流，以便快速发现附近感兴趣的线下活动 | P0 | 3 | Sprint 1 | Done |
| US-02 | User Story | 作为用户，我想注册和登录账号，以便报名活动、发布活动和管理个人信息 | P0 | 5 | Sprint 1 | In Progress |
| US-03 | User Story | 作为用户，我想查看活动详情，以便了解活动时间、地点、人数上限和准备事项 | P0 | 3 | Sprint 1 | Done |
| UI-01 | Task | 制定 Gatherly 页面统一样式规范 | P1 | 2 | Sprint 1 | Done |
| DOC-01 | Documentation | 编写 README 项目说明文档 | P1 | 2 | Sprint 1 | Done |
| DOC-02 | Documentation | 整理 Sprint 1 会议记录与 GitHub 截图 | P1 | 1 | Sprint 1 | In Progress |
| US-04 | User Story | 作为活动发布者，我想发布线下活动，以便邀请同好一起参加 | P0 | 5 | Sprint 2 | Product Backlog |
| US-05 | User Story | 作为登录用户，我想一键报名活动，以便参加自己感兴趣的线下活动 | P0 | 5 | Sprint 2 | In Progress |
| US-06 | User Story | 作为用户，我想按兴趣标签筛选活动，以便快速找到符合兴趣的内容 | P1 | 3 | Sprint 2 | In Progress |
| US-07 | User Story | 作为用户，我想进入同好圈，以便和相同兴趣的人交流经验 | P1 | 5 | Sprint 2 | Product Backlog |
| US-08 | User Story | 作为用户，我想发布圈子帖子，以便分享经验或发起临时约伴 | P1 | 5 | Sprint 2 | Product Backlog |
| US-09 | User Story | 作为用户，我想在活动结束后评分，以便帮助其他用户判断活动质量 | P1 | 3 | Sprint 2 | Product Backlog |

## Sprint 1 Backlog

Sprint 1 目标：完成项目基础框架和核心页面雏形，让 Gatherly Web 可以进入核心业务功能开发阶段。

| 编号 | 任务 | 优先级 | 故事点 | 看板状态 |
|---|---|---|---|---|
| TASK-01 | 搭建 Flask 基础项目结构 | P0 | 3 | Done |
| TASK-02 | 设计基础数据库模型 | P0 | 3 | In Progress |
| TASK-03 | 设计活动报名业务流程 | P1 | 2 | In Progress |
| TASK-04 | 清理项目冗余文件并优化 docs 文档结构 | P1 | 2 | In Progress |
| US-01 | 首页活动流展示 | P0 | 3 | Done |
| US-02 | 用户注册与登录 | P0 | 5 | In Progress |
| US-03 | 活动详情页面 | P0 | 3 | Done |
| UI-01 | 制定页面统一样式规范 | P1 | 2 | Done |
| DOC-01 | 编写 README 项目说明文档 | P1 | 2 | Done |
| DOC-02 | 整理 Sprint 1 会议记录与 GitHub 截图 | P1 | 1 | In Progress |

## Sprint 2 候选 Backlog

Sprint 2 目标：完善 Gatherly 的核心业务闭环和特色功能。

| 编号 | 任务 | 优先级 | 故事点 | 当前状态 |
|---|---|---|---|---|
| US-04 | 活动发布功能 | P0 | 5 | Product Backlog |
| US-05 | 活动报名功能 | P0 | 5 | In Progress |
| US-06 | 兴趣标签筛选活动 | P1 | 3 | In Progress |
| US-07 | 同好圈页面 | P1 | 5 | Product Backlog |
| US-08 | 圈子发帖功能 | P1 | 5 | Product Backlog |
| US-09 | 活动评分功能 | P1 | 3 | Product Backlog |

## 后续可选加分功能

| 编号 | 用户故事 / 任务 | 优先级 | 故事点 |
|---|---|---|---|
| US-10 | 作为用户，我想查看个人主页，以便展示兴趣标签和参与过的活动 | P1 | 3 |
| US-11 | 作为管理员，我想审核用户发布的活动，以便减少虚假或违规内容 | P1 | 5 |
| US-12 | 作为商家，我想申请官方认证，以便提升活动可信度 | P2 | 5 |
| US-13 | 作为用户，我想收到活动满员提醒，以便及时了解报名状态 | P2 | 3 |
| US-14 | 作为平台，我想根据履约评分限制低评分用户发起活动，以便维护平台秩序 | P2 | 8 |
| US-15 | 作为用户，我想使用私信联系同好，以便进一步沟通活动细节 | P2 | 8 |

## 当前分工建议

| 成员 | 负责 Issue | 主要内容 |
|---|---|---|
| 组长 | TASK-01 / TASK-04 | Flask 基础结构、仓库管理、项目清理和文档结构 |
| 成员A | US-01 / UI-01 | 首页活动流、卡片样式、移动端首页 |
| 成员B | US-03 / UI-01 | 活动详情页、页面样式统一 |
| 成员C | US-02 | 用户注册、登录、退出、登录状态 |
| 成员D | TASK-03 / US-05 | 活动报名流程、人数限制、报名记录 |
| 成员E | TASK-02 | 数据库表结构设计 |
| 成员F | DOC-01 / DOC-02 | README、会议记录、截图整理 |

## 维护规则

- 新需求先进入 Product Backlog。
- Sprint 开始时再把任务移动到对应 Sprint Backlog。
- 每个 Backlog 条目应对应 GitHub Issue。
- 状态应与 GitHub Project 保持一致。
- 文档类任务使用 Documentation 类型，缺陷修复使用 Bug 类型。
# 历史归档，仅供参考

> 本文件为本次文档整理前的旧版 Backlog 材料，保留为过程证据。当前功能范围请以 [../feature-guide.md](../feature-guide.md) 和当前 GitHub Issues 为准。
