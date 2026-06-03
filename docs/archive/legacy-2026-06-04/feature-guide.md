# 功能说明

本文档按模块说明当前仓库代码中已经存在的功能。功能范围以 `app/routes/`、`app/templates/` 和 `app/models.py` 为准。

## 账号与认证

相关文件：

- `app/routes/auth.py`
- `app/forms.py`
- `app/utils/email_verification.py`
- `app/templates/register.html`
- `app/templates/login.html`
- `app/templates/forgot_password.html`
- `app/templates/account_settings.html`

当前能力：

- 用户注册。
- 用户名或邮箱登录。
- 登出。
- 找回密码。
- 修改邮箱。
- 修改密码。
- 账号注销。
- 登录失败次数限制。
- 注册、改邮箱、改密码、重置密码时使用邮箱验证码。
- 本地开发可使用 console 邮件模式，验证码打印到控制台。
- 支持 Brevo Transactional Email API 和 SMTP 发送验证码。
- 商家认证申请入口。

## 活动发现

相关文件：

- `app/routes/activity.py`
- `app/templates/index.html`
- `app/templates/activity_detail.html`
- `app/static/js/main.js`

当前能力：

- 首页活动流展示。
- 活动卡片展示标题、描述、时间、地点、人数、标签、评分等信息。
- 按兴趣分类、日期、城市和关键词筛选活动。
- 搜索建议接口 `/search/suggestions`。
- 搜索结果页 `/search`，覆盖活动、圈子和用户。
- 活动详情页展示活动基本信息、组织者、报名情况、评论区和参与者反馈入口。

## 活动发布与管理

相关文件：

- `app/routes/activity.py`
- `app/templates/activity_create.html`

当前能力：

- 登录用户可以发布活动。
- 活动字段包括标题、简介、详情、城市、地点、开始/结束时间、时区、人数上限、费用、标签、关联圈子、准备事项和活动图片。
- 活动发布后，发起者自动生成报名记录。
- 信任分低于阈值的用户不能发布活动。
- 管理员或已认证商家可以发布官方认证或优质活动。
- 活动组织者或管理员可以关闭/取消活动。
- 活动可更新标签和关联圈子。

## 报名与参与

相关文件：

- `app/routes/activity.py`
- `app/models.py`

当前能力：

- 用户报名活动。
- 防止重复报名。
- 活动满员时禁止继续报名。
- 活动过期或非开放状态时禁止报名。
- 活动开始前，非组织者可取消报名。
- 报名状态支持 `registered`、`cancelled` 等状态。

## 活动收藏与评论

相关模型：

- `ActivityFavorite`
- `Comment`
- `Interaction`

当前能力：

- 登录用户可以收藏/取消收藏活动。
- 活动详情页支持评论。
- 评论状态可被后台管理。

## 同好圈

相关文件：

- `app/routes/circle.py`
- `app/templates/circle.html`
- `app/templates/circle_detail.html`
- `app/templates/create_circle.html`
- `app/templates/create_post.html`
- `app/static/js/circle.js`

当前能力：

- 展示系统同好圈和用户创建的同好圈。
- 用户创建圈子。
- 用户加入或退出圈子。
- 私密圈访问申请与审批。
- 圈主可设置公告、封面、成员角色、转让圈主。
- 圈内帖子发布。
- 帖子置顶。
- 帖子图片。
- 评论、回复和评论图片。
- 帖子与评论的点赞、收藏、分享互动记录。

## 私信

相关文件：

- `app/routes/messages.py`
- `app/templates/messages.html`

当前能力：

- 私信会话列表。
- 用户之间发送文字私信。
- 用户之间发送图片私信。
- 会话轮询接口。
- 会话隐藏。
- 会话删除。
- 消息已读状态。
- 未读私信计数。
- 消息过期清理。
- 非互相关注状态下限制连续发送第一条私信；对方回复或互相关注后可继续交流。

## 通知

相关文件：

- `app/routes/notifications.py`
- `app/templates/notifications.html`

当前能力：

- 通知列表。
- 单条通知标记已读。
- 全部通知标记已读。
- 未读通知计数。
- 通知过期清理。
- 通知可关联活动、圈子和商家认证。

## 用户主页与社交关系

相关文件：

- `app/routes/profile.py`
- `app/templates/profile.html`
- `app/templates/edit_profile.html`
- `app/templates/users.html`
- `app/templates/follows.html`

当前能力：

- 个人主页。
- 编辑昵称、城市、简介、兴趣和头像。
- 主页可见性设置。
- 创建的活动、报名的活动、加入的圈子、帖子、评论、互动记录分区展示。
- 用户搜索。
- 关注和取消关注。
- 粉丝和关注列表。
- 附近的人，根据城市、请求头或粗略 IP 信息进行弱匹配。

## 评分与信任机制

相关模型：

- `Review`
- `ActivityReview`
- `UserReview`
- `TrustScoreLog`

当前能力：

- 兼容旧流程的活动评分模型 `Review`。
- 新的活动多维评分模型 `ActivityReview`。
- 活动结束后，实际参与者可对其他参与者互评。
- 参与者互评包括准时、友好、沟通、可靠、尊重、安全等维度。
- 收到互评后，用户信任分会按平均分重新计算。
- 信任分变化写入 `TrustScoreLog`。

## 管理员系统

相关文件：

- `app/routes/admin.py`
- `app/templates/admin_*.html`

当前能力：

- 管理员仪表盘。
- 管理日志。
- 用户搜索、封禁、解封、设为管理员、撤销管理员。
- 商家资质授予和撤销。
- 活动状态管理、活动加精。
- 圈子隐藏、恢复、置顶、删除。
- 帖子隐藏、恢复、删除。
- 评论隐藏、恢复、删除。
- 管理员账号信息维护。
- 商家认证申请审核。

## 待优化功能

- 自动化测试覆盖不足。
- 数据库迁移目前依赖 SQLite 兼容性 helper，长期应改为正式迁移工具。
- 部分 Python 源码中的历史中文文案存在编码损坏，需要单独 Issue 修复。
- 附近的人目前是粗略位置匹配，不应视为精确地理定位。
- 上传文件的生产环境存储、清理和备份策略需要继续完善。

