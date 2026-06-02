# 数据库设计

本文档基于当前 `app/models.py` 重新整理，旧文档和旧 ER 图不再作为事实来源。

## 数据库技术

- ORM：Flask-SQLAlchemy
- 本地数据库：SQLite
- 数据库 URI：`sqlite:///gatherly.db`
- 本地数据库文件位置：Flask `instance/` 目录下的 `gatherly.db`
- 初始化入口：`init_db.py`
- 模型定义：`app/models.py`

当前代码包含若干 SQLite schema 兼容函数，例如 `ensure_user_account_schema()`、`ensure_activity_schema()`、`ensure_task_foundation_schema()` 等，用于在开发期把旧本地数据库补齐到当前字段。长期生产化建议改为正式迁移工具。

## ER 图

Mermaid 源文件：

- [er-diagram.mmd](er-diagram.mmd)

GitHub 可以直接预览 Mermaid 代码块，也可以使用 Mermaid 工具将 `.mmd` 渲染为 SVG 或 PNG。

## 主要实体

### User

用户账号表，保存用户名、昵称、邮箱、邮箱验证时间、密码哈希、头像、简介、兴趣、城市、附近的人开关、粗略定位信息、角色、信任分、状态和创建时间。

关键关系：

- 一个用户可以创建多个活动。
- 一个用户可以报名多个活动。
- 一个用户可以发布多个帖子和评论。
- 一个用户可以发送和接收多条私信。
- 一个用户可以关注多个用户，也可以被多个用户关注。
- 一个用户可以有一个主页可见性配置。
- 一个用户可以提交和接收参与者互评。
- 一个用户可以收到多条通知。

唯一约束：

- `username`
- `email`

### Activity

活动表，保存标题、简介、详情、城市、地点、开始和结束时间、时区、人数上限、初始人数、图片、费用、标签、关联圈子、状态、取消信息、是否精选、是否官方、发起者和准备事项。

关键关系：

- 一个用户可以创建多个活动。
- 一个活动属于一个发起者。
- 一个活动可以关联一个同好圈。
- 一个活动可以有多个报名记录。
- 一个活动可以有多个收藏、评论、兼容旧评分、新活动评分和参与者互评。

### Registration

活动报名表，连接用户和活动，记录报名状态、取消原因、取消时间和报名时间。

关键关系：

- 一个用户可以有多条报名记录。
- 一个活动可以有多条报名记录。

当前模型没有定义数据库级唯一约束防止重复报名，重复报名主要由路由逻辑处理。

### ActivityFavorite

活动收藏表，连接用户和活动。

唯一约束：

- `user_id + activity_id`

### Circle

同好圈表，保存名称、标签、封面、简介、公告、圈主、置顶帖子、是否置顶、是否系统圈、初始成员数、成员数、状态和时间戳。

关键关系：

- 一个圈子可以有多个帖子。
- 一个圈子可以有多个活动。
- 一个圈子可以有多个成员记录。
- 一个圈子可以有一个圈主。
- 一个圈子可以置顶一个帖子。

### CircleMember

同好圈成员表，连接用户和圈子，保存角色、状态、加入时间和更新时间。

唯一约束：

- `circle_id + user_id`

### Post

圈内帖子表，保存标题、内容、类型、状态、作者和所属圈子。

关键关系：

- 一个用户可以发布多个帖子。
- 一个圈子可以包含多个帖子。
- 一个帖子可以有多个评论和图片。

### PostImage

帖子图片表，连接帖子和图片路径。

### Comment

统一评论表，可评论活动或帖子，也支持自引用回复。

关键关系：

- 一个用户可以发布多条评论。
- 一条评论可以属于一个活动或一个帖子。
- 一条评论可以回复另一条评论。
- 一条评论可以有多张评论图片。

检查约束：

- `activity_id` 和 `post_id` 必须且只能有一个非空。

### CommentImage

评论图片表，连接评论和图片路径。

### Interaction

通用互动表，用于记录点赞、收藏、分享等行为。通过 `target_type` 和 `target_id` 指向目标对象。

唯一约束：

- `user_id + target_type + target_id + action_type`

### Review

旧活动评分兼容表。当前 `models.py` 明确标注该模型用于兼容旧活动路由流程，后续可逐步迁移到 `ActivityReview`。

### ActivityReview

活动多维评分表，包含组织、场地、内容、性价比、体验、平均分、评论和状态。

唯一约束：

- `activity_id + reviewer_id`

### UserReview

参与者互评表，记录同一活动中用户对其他参与者的评分，包含准时、友好、沟通、可靠、尊重、安全和平均分。

唯一约束：

- `activity_id + reviewer_id + reviewee_id`

检查约束：

- 六个评分字段都要求在 1 到 5 之间。

### TrustScoreLog

信任分日志表，记录用户信任分变化、操作人、变化类型、分值前后、原因和关联对象。

### ProfileVisibility

用户主页可见性配置表，控制主页、活动、圈子、评价、信任分、兴趣和互动是否展示。

唯一约束：

- `user_id`

### AdminLog

管理员操作日志表，记录管理员、动作、目标类型、目标 ID、详情、IP 和时间。

### EmailVerificationCode

邮箱验证码表，保存用户、邮箱、验证码哈希、用途、过期时间、使用时间和创建时间。

用途包括：

- 注册
- 修改邮箱
- 修改密码
- 重置密码

### Notification

通知表，保存接收者、类型、标题、内容、关联对象、已读时间、过期时间和创建时间。

### DirectMessage

私信表，保存发送者、接收者、内容、消息类型、图片路径、已读时间、过期时间和创建时间。

### DirectMessageConversationState

私信会话状态表，按用户和对方用户保存隐藏、删除、清空和更新时间。

唯一约束：

- `user_id + other_user_id`

检查约束：

- `user_id != other_user_id`

### UserFollow

用户关注表，保存关注者和被关注者。

唯一约束：

- `follower_id + followed_id`

检查约束：

- `follower_id != followed_id`

### MerchantVerification

商家认证表，保存申请用户、商家名称、证照编号、文件路径、申请原因、联系方式、状态、拒绝原因、审核管理员和审核时间。

## 关系概览

- `User` 1 对多 `Activity`
- `User` 1 对多 `Registration`
- `Activity` 1 对多 `Registration`
- `User` 多对多 `Activity`，通过 `Registration` 表实现报名
- `User` 多对多 `Activity`，通过 `ActivityFavorite` 表实现收藏
- `Circle` 1 对多 `Activity`
- `Circle` 1 对多 `Post`
- `User` 1 对多 `Post`
- `Circle` 多对多 `User`，通过 `CircleMember` 表实现成员关系
- `Post` 1 对多 `Comment`
- `Activity` 1 对多 `Comment`
- `Comment` 1 对多 `Comment`，实现回复
- `User` 1 对多 `DirectMessage` 发送关系
- `User` 1 对多 `DirectMessage` 接收关系
- `User` 多对多 `User`，通过 `UserFollow` 表实现关注
- `User` 1 对多 `Notification`
- `User` 1 对多 `MerchantVerification` 申请关系
- `User` 1 对多 `MerchantVerification` 审核关系
- `Activity` 1 对多 `ActivityReview`
- `Activity` 1 对多 `UserReview`
- `User` 1 对多 `TrustScoreLog`

## 设计注意事项

- 当前本地数据库是 SQLite，迁移依赖代码中的兼容函数，不是正式迁移系统。
- 上传文件只在数据库中保存路径，真实文件位于 `app/static/` 下的图片或上传目录。
- `Interaction` 使用 `target_type + target_id`，不是强外键关系。
- `Notification.related_type + related_id` 也是弱关联。
- `Review` 是兼容模型，新的评分设计主要是 `ActivityReview` 和 `UserReview`。
- 部分唯一性依赖路由逻辑，例如报名重复限制；后续可考虑补充数据库级唯一约束。

