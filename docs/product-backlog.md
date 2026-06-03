# Product Backlog

最后更新时间：2026-06-04

本文根据当前 GitHub Issues、历史归档资料和当前代码功能模块整理。Issue 数字编号沿用 GitHub 仓库真实编号，不重新编号。GitHub connector 当前能读取 Issue 编号、标题和正文；labels、milestone、assignee 未完整返回的条目标记为“待同步”。

## 分类说明

| 类型 | 说明 |
|---|---|
| User Story | 从用户角度描述可验收的产品能力 |
| Task | 技术任务、结构搭建、流程设计或配置任务 |
| Bug | 已发现的缺陷或异常数据清理 |
| Documentation | README、docs、截图、测试记录、演示材料 |
| Enhancement | 已有功能体验优化 |
| UI / Style | 样式规范、页面视觉和移动端体验 |

## 优先级说明

| 优先级 | 含义 |
|---|---|
| P0 | 核心闭环必需，缺失会影响主要演示 |
| P1 | 重要功能或交付材料，影响完整度和质量 |
| P2 | 可选优化或加分项 |

## Product Backlog 总表

| Issue 编号 | 类型 | 模块 | 用户故事 / 任务说明 | 优先级 | Milestone | 负责人 | 状态 | 主要修改文件 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| #4 TASK-01 | Task | 项目基础 | 搭建 Flask 基础项目结构 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/`, `run.py`, `requirements.txt` | 项目可通过 `python run.py` 启动 |
| #5 TASK-02 | Task | 数据库 | 设计用户、活动、报名、圈子、帖子、评分等基础数据模型 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/models.py`, `migrations/` | 模型能支撑当前核心功能 |
| #6 TASK-03 | Task | 活动报名 | 设计活动报名业务流程 | P1 | Sprint 1 - Basic Framework | 待同步 | Done | `app/routes/activity.py`, docs | 报名规则清晰，覆盖登录、重复、满员和异常情况 |
| #7 US-01-01 | User Story | 首页活动流 | 作为游客，我想要浏览首页活动卡片，以便于快速了解当前有哪些线下活动。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/index.html`, `app/routes/activity.py` | 首页展示活动卡片 |
| #8 US-01-02 | User Story | 首页活动流 | 作为游客，我想要查看活动标题、时间、地点和人数，以便于快速判断是否适合参加。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/index.html` | 活动卡片展示基本信息 |
| #9 US-01-03 | User Story | 首页活动流 | 作为游客，我想要查看活动图片和兴趣标签，以便于判断活动氛围和兴趣匹配度。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/index.html`, `app/static/images/` | 图片和标签显示正常 |
| #10 UI-01 | UI / Style | 全站样式 | 制定 Gatherly 页面统一样式规范 | P1 | Sprint 1 - Basic Framework | 待同步 | Done | `app/static/css/style.css` | 按钮、卡片、标签、导航风格统一 |
| #11 DOC-01 | Documentation | README | 编写 README 项目说明文档 | P1 | Sprint 1 - Basic Framework | 待同步 | Open | `README.md` | README 能说明背景、功能、技术栈和运行方式 |
| #12 DOC-02 | Documentation | 会议记录 | 整理 Sprint 1 会议记录与 GitHub 截图 | P1 | Sprint 1 - Basic Framework | 待同步 | Open | `docs/meeting-notes.md`, `docs/screenshots/` | 会议记录和截图材料完整 |
| #13 US-01-04 | User Story | 首页活动流 | 作为游客，我想要点击活动卡片进入详情页，以便于进一步查看完整活动信息。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/index.html`, `app/routes/activity.py` | 点击活动卡片跳转详情 |
| #14 US-02-01 | User Story | 注册登录 | 作为游客，我想要注册账号，以便于使用报名、发帖和个人主页等功能。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/routes/auth.py`, `app/templates/register.html` | 注册信息可保存并有错误提示 |
| #15 US-02-02 | User Story | 注册登录 | 作为已注册用户，我想要登录账号，以便于进入个人状态并使用平台功能。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/routes/auth.py`, `app/templates/login.html` | 正确账号可登录，错误账号有提示 |
| #16 US-02-03 | User Story | 注册登录 | 作为已登录用户，我想要退出当前账号，以便于保护个人账号安全。 | P1 | Sprint 1 - Basic Framework | 待同步 | Done | `app/routes/auth.py`, `app/templates/base.html` | 退出后清除登录状态 |
| #17 US-02-04 | User Story | 注册登录 | 作为已登录用户，我想要页面显示我的用户名，以便于确认当前登录状态。 | P1 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/base.html` | 登录和未登录状态显示不同 |
| #18 US-03-01 | User Story | 活动详情 | 作为用户，我想要查看活动完整介绍，以便于判断活动内容是否符合兴趣。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/activity_detail.html` | 详情页显示标题和介绍 |
| #19 US-03-02 | User Story | 活动详情 | 作为用户，我想要查看活动时间和地点，以便于安排出行和时间。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/activity_detail.html` | 时间地点显示清楚 |
| #20 US-03-03 | User Story | 活动详情 | 作为用户，我想要查看人数上限和报名状态，以便于判断是否还能报名。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/activity_detail.html`, `app/models.py` | 人数信息不超过上限 |
| #21 US-03-04 | User Story | 活动详情 | 作为用户，我想要查看准备事项，以便于提前准备物品。 | P1 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/activity_detail.html`, `app/models.py` | 准备事项展示正常 |
| #22 US-03-05 | User Story | 活动详情 | 作为用户，我想要看到明显的立即报名按钮，以便于快速参与活动。 | P0 | Sprint 1 - Basic Framework | 待同步 | Done | `app/templates/activity_detail.html` | 报名按钮清晰且移动端可点击 |
| #23-#27 US-04 | User Story | 活动发布 | 作为活动发布者，我想要填写活动信息并发布活动，以便于邀请同好参加。 | P0 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/activity.py`, `app/templates/activity_create.html`, `app/models.py` | 登录用户可发布活动，字段保存并展示 |
| #28-#33 US-05 | User Story | 活动报名 | 作为登录用户，我想要报名活动，以便于参加感兴趣的线下活动。 | P0 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/activity.py`, `app/models.py` | 未登录、重复、满员、过期等情况被正确处理 |
| #34-#39 US-06 | User Story | 标签筛选 | 作为用户，我想要按标签筛选活动，以便于快速找到符合兴趣的内容。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/activity.py`, `app/templates/index.html` | 标签筛选、当前选中和恢复全部可用 |
| #40-#46 US-07 | User Story | 同好圈 | 作为用户，我想要浏览和加入同好圈，以便于和相同兴趣的人交流。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/circle.py`, `app/templates/circle.html`, `app/templates/circle_detail.html` | 圈子列表、详情、加入和成员信息正常 |
| #47-#53 US-08 | User Story | 圈子帖子 | 作为圈子成员，我想要发布帖子和评论，以便于分享经验或讨论。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/circle.py`, `app/templates/create_post.html`, `app/templates/circle_detail.html` | 发帖、评论、图片和互动可用 |
| #54 DOC-03 | Documentation | 演示材料 | 整理最终演示视频素材 | P1 | Final Delivery | 待同步 | Open | `docs/screenshots/`, `docs/meeting-notes.md` | 核心页面截图和演示脚本准备完成 |
| #55 DOC-04 | Documentation | README | 完善最终 README 文档 | P1 | Final Delivery | 待同步 | Open | `README.md`, `docs/` | README 与最终项目一致 |
| #56 TEST-01 | Task | 测试 | 完成项目功能测试 | P0 | Final Delivery | 待同步 | Open | `docs/test-report.md` | 主要页面和流程可人工验证 |
| #57 DOC-05 | Documentation | 个人报告材料 | 整理个人实验报告材料 | P1 | Final Delivery | 待同步 | Open | `docs/screenshots/`, `docs/meeting-notes.md` | 每位成员材料可追踪 |
| #85 DOC-06 | Documentation | 新增功能文档 | 补充新增功能说明、截图和测试记录 | P1 | Final Delivery | 待同步 | Open | `README.md`, `docs/database-design.md`, `docs/test-report.md` | 新增功能说明和测试记录完整，且不修改业务代码 |
| #118 | Task | 未分类 | Add new log | P2 | 待同步 | 待同步 | Open | 待确认 | 需补充标题编号、类型、验收标准 |
| #159 BUG-02 | Bug | 同好圈 | 清理同好圈测试圈子和异常数据来源 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/circle.py`, seed / 初始化数据 | 不影响正常系统圈子和用户自定义圈子 |
| #162 US-16-05 | User Story | 管理员后台 | 作为管理员，我想要修改自己的后台账号信息，以便于维护管理员账号。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/admin.py`, `app/templates/admin_account.html` | 管理员可修改自身资料，普通用户不可访问 |
| #164 US-16-04 | User Story | 管理员后台 | 作为管理员，我想要封禁和解封用户，以便于维护社区秩序。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/admin.py`, `app/routes/auth.py`, `app/templates/admin_users.html` | 封禁用户不可登录，解封后恢复 |
| #170 US-16-06 | User Story | 管理员后台 | 作为管理员，我想要授予和撤销管理员权限，以便于多人维护平台。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/admin.py`, `app/templates/admin_users.html` | 至少保留一个管理员，操作写入日志 |
| #172 US-16-07 | User Story | 管理员后台 | 作为管理员，我想要管理圈子、帖子和评论，以便于处理违规内容。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/admin.py`, `app/templates/admin_*.html` | 管理员可查看、隐藏、删除内容 |
| #173 US-18-01 | User Story | 个人主页 | 作为已登录用户，我想要管理自己的帖子和评论，以便于回顾和删除个人内容。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/profile.py`, `app/templates/profile*.html` | 只能管理自己的内容 |
| #176 US-16-08 | User Story | 管理员后台 | 作为管理员，我想要搜索和筛选后台列表，以便于快速定位内容。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/admin.py`, `app/templates/admin_*.html` | 搜索筛选不影响原管理功能 |
| #177 US-18-02 | User Story | 个人主页 | 作为已登录用户，我想要搜索和筛选自己的内容，以便于快速找到历史内容。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/profile.py`, `app/templates/profile_section.html` | 搜索结果只返回当前用户内容 |
| #181 ENH-03 | Enhancement | 全站提醒 | 优化全站 flash/message 提醒自动消失 | P2 | Final Delivery | 待同步 | Done | `app/templates/base.html`, `app/static/js/main.js`, `app/static/css/style.css` | 消息自动淡出且不影响现有 flash |
| #182 US-18-03 | User Story | 个人资料 | 作为已登录用户，我想要编辑个人简介和兴趣标签，以便于展示个人信息。 | P1 | Sprint 2 - Core Features | 待同步 | Done | `app/routes/profile.py`, `app/templates/edit_profile.html`, `app/models.py` | 保存后个人主页展示最新资料 |

## 当前开放 Issue

| Issue | 类型 | 当前处理建议 |
|---|---|---|
| #11 DOC-01 | Documentation | 已由当前英文 README 更新覆盖，合并前核对是否需要关闭 |
| #12 DOC-02 | Documentation | 需要补充真实 GitHub 截图到 `docs/screenshots/` |
| #54 DOC-03 | Documentation | 需要准备演示脚本和核心页面截图 |
| #55 DOC-04 | Documentation | 当前任务已更新 README 和 docs，可作为验收依据 |
| #56 TEST-01 | Task | 需要人工完成浏览器功能测试并补充截图 |
| #57 DOC-05 | Documentation | 需要每位成员自行补充个人报告截图和 PR 链接 |
| #85 DOC-06 | Documentation | 当前任务已补充新增功能文档、数据库和测试说明；截图仍需人工补齐 |
| #118 未编号 | Task | 建议重新命名为规范标题或关闭无效 Issue |

## 维护规则

- 不要重排 GitHub Issue 的数字编号。
- Backlog 中的 `US-XX-XX`、`TASK-XX`、`BUG-XX`、`DOC-XX`、`UI-XX`、`ENH-XX` 应与 Issue 标题保持一致。
- 新任务先进入 Product Backlog，再由会议决定是否进入当前 Sprint。
- Issue 状态、Label、Milestone 和 Project Board 变更后，应同步更新本文。
- 文档任务不得混入业务功能修改，除非该文档是对应功能 Issue 的验收项。
