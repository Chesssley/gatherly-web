# Gatherly Product Backlog

本文件记录 Gatherly 项目的产品待办列表。Product Backlog 包含项目从启动到最终交付所需完成的用户故事、技术任务和文档任务。

Gatherly 是一个面向小众兴趣爱好者的线下活动聚合与同好匹配平台，核心目标是解决用户“想玩但找不到同好、不知道去哪玩”的问题。项目围绕活动发现、活动发布、活动报名、同好圈交流、评分信任机制等功能展开。

---

## 一、优先级说明

| 优先级 | 含义 |
|---|---|
| P0 | 必须完成，没有该功能项目无法形成基本闭环 |
| P1 | 重要功能，能够体现项目特色 |
| P2 | 加分功能，时间允许时完成 |

---

## 二、故事点说明

| 故事点 | 难度说明 |
|---|---|
| 1 | 极简单，少量修改或文档整理 |
| 2 | 简单，静态页面、流程设计或基础文档任务 |
| 3 | 中等，需要页面展示、数据设计或简单交互 |
| 5 | 较复杂，涉及表单、数据库、登录状态或业务规则 |
| 8 | 复杂，涉及多个模块联动，当前阶段暂不优先开发 |

---

## 三、Product Backlog 总表

| 编号 | 类型 | 用户故事 / 任务 | 优先级 | 故事点 | Sprint | 当前状态 |
|---|---|---|---|---|---|---|
| TASK-01 | 技术任务 | 搭建 Flask 基础项目结构 | P0 | 3 | Sprint 1 | In Progress |
| TASK-02 | 技术任务 | 设计用户表、活动表、报名表、圈子表、帖子表、评分表 | P0 | 3 | Sprint 1 | Sprint Backlog |
| TASK-03 | 技术任务 | 设计活动报名业务流程 | P1 | 2 | Sprint 1 | Sprint Backlog |
| US-01 | 用户故事 | 作为游客，我想浏览首页活动流，以便快速发现附近感兴趣的线下活动 | P0 | 3 | Sprint 1 | Sprint Backlog |
| US-02 | 用户故事 | 作为用户，我想注册和登录账号，以便报名活动、发布活动和管理个人信息 | P0 | 5 | Sprint 1 | Sprint Backlog |
| US-03 | 用户故事 | 作为用户，我想查看活动详情，以便了解活动时间、地点、人数上限和准备事项 | P0 | 3 | Sprint 1 | Sprint Backlog |
| UI-01 | 技术任务 | 制定 Gatherly 页面统一样式规范 | P1 | 2 | Sprint 1 | Sprint Backlog |
| DOC-01 | 文档任务 | 编写 README 项目说明文档 | P1 | 2 | Sprint 1 | Sprint Backlog |
| DOC-02 | 文档任务 | 整理 Sprint 1 会议记录与 GitHub 截图 | P1 | 1 | Sprint 1 | Sprint Backlog |
| US-04 | 用户故事 | 作为活动发布者，我想发布线下活动，以便邀请同好一起参与 | P0 | 5 | Sprint 2 | Product Backlog |
| US-05 | 用户故事 | 作为登录用户，我想一键报名活动，以便参加自己感兴趣的线下活动 | P0 | 5 | Sprint 2 | Product Backlog |
| US-06 | 用户故事 | 作为用户，我想按兴趣标签筛选活动，以便快速找到符合自己兴趣的内容 | P1 | 3 | Sprint 2 | Product Backlog |
| US-07 | 用户故事 | 作为用户，我想进入同好圈，以便和相同兴趣的人交流经验 | P1 | 5 | Sprint 2 | Product Backlog |
| US-08 | 用户故事 | 作为用户，我想发布圈子帖子，以便分享经验或发起临时约伴 | P1 | 5 | Sprint 2 | Product Backlog |
| US-09 | 用户故事 | 作为用户，我想在活动结束后进行评分，以便帮助其他用户判断活动质量 | P1 | 3 | Sprint 2 | Product Backlog |

---

## 四、Sprint 1 Backlog

Sprint 1 目标：完成项目基础框架和核心页面雏形，让 Gatherly 可以进入实际功能开发阶段。

| 编号 | 任务 | 优先级 | 故事点 | 看板状态 |
|---|---|---|---|---|
| TASK-01 | 搭建 Flask 基础项目结构 | P0 | 3 | In Progress |
| TASK-02 | 设计用户表、活动表、报名表、圈子表、帖子表、评分表 | P0 | 3 | Sprint Backlog |
| TASK-03 | 设计活动报名业务流程 | P1 | 2 | Sprint Backlog |
| US-01 | 首页活动流展示 | P0 | 3 | Sprint Backlog |
| US-02 | 用户注册与登录 | P0 | 5 | Sprint Backlog |
| US-03 | 活动详情页面 | P0 | 3 | Sprint Backlog |
| UI-01 | 制定 Gatherly 页面统一样式规范 | P1 | 2 | Sprint Backlog |
| DOC-01 | 编写 README 项目说明文档 | P1 | 2 | Sprint Backlog |
| DOC-02 | 整理 Sprint 1 会议记录与 GitHub 截图 | P1 | 1 | Sprint Backlog |

---

## 五、Sprint 2 Backlog 候选

Sprint 2 目标：完成 Gatherly 的核心业务闭环和项目特色功能。

| 编号 | 任务 | 优先级 | 故事点 | 当前状态 |
|---|---|---|---|---|
| US-04 | 活动发布功能 | P0 | 5 | Product Backlog |
| US-05 | 活动报名功能 | P0 | 5 | Product Backlog |
| US-06 | 兴趣标签筛选活动 | P1 | 3 | Product Backlog |
| US-07 | 同好圈页面 | P1 | 5 | Product Backlog |
| US-08 | 圈子发帖功能 | P1 | 5 | Product Backlog |
| US-09 | 活动评分功能 | P1 | 3 | Product Backlog |

---

## 六、后续可选加分功能

| 编号 | 用户故事 / 任务 | 优先级 | 故事点 |
|---|---|---|---|
| US-10 | 作为用户，我想查看个人主页，以便展示兴趣标签和参与过的活动 | P1 | 3 |
| US-11 | 作为管理员，我想审核用户发布的活动，以便减少虚假或违规内容 | P1 | 5 |
| US-12 | 作为商家，我想申请官方认证，以便提升活动可信度 | P2 | 5 |
| US-13 | 作为用户，我想收到活动满员提醒，以便及时了解报名状态 | P2 | 3 |
| US-14 | 作为平台，我想根据用户履约评分限制低评分用户发起活动，以便维护平台秩序 | P2 | 8 |
| US-15 | 作为用户，我想使用私信联系同好，以便进一步沟通活动细节 | P2 | 8 |

---

## 七、当前 Sprint 1 分工建议

| 成员 | 负责 Issue | 主要内容 |
|---|---|---|
| 组长 | TASK-01 | Flask 基础项目结构、GitHub 协作管理 |
| 成员A | US-01 / UI-01 | 首页活动流、卡片样式、移动端首页 |
| 成员B | US-03 / UI-01 | 活动详情页、页面样式统一 |
| 成员C | US-02 | 用户注册、登录、退出、登录状态 |
| 成员D | TASK-03 | 活动报名业务流程设计 |
| 成员E | TASK-02 | 数据库表结构设计 |
| 成员F | DOC-01 / DOC-02 | README、会议记录、截图整理 |

---

## 八、备注

本 Product Backlog 会随着 Sprint 推进持续更新。Sprint 1 结束后，将根据完成情况把 Sprint 2 候选任务移动到 Sprint 2 Backlog，并继续补充 Review 和 Retrospective 记录。
