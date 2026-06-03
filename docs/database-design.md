# 数据库设计

最后更新时间：2026-06-04

本文件根据当前 `app/models.py` 重新整理，反映当前代码版本的数据结构。旧文档和旧 ER 图不再作为事实来源。

## 数据库技术

| 项目 | 当前实现 |
|---|---|
| ORM | Flask-SQLAlchemy |
| 迁移工具 | Flask-Migrate / Alembic |
| 默认数据库 | SQLite |
| 推荐线上数据库 | Neon PostgreSQL，通过 `DATABASE_URL` 配置 |
| 默认 URI | `sqlite:///gatherly.db` |
| 默认数据库位置 | Flask instance 目录下的 `gatherly.db` |
| 可选数据库 | 其他 PostgreSQL 兼容数据库 |
| 模型定义文件 | `app/models.py` |
| 初始化脚本 | `init_db.py` |

ER 图见：[er-diagram.md](er-diagram.md)。

## 当前模型总览

| 模型类 | 表名 | 业务含义 |
|---|---|---|
| `User` | `user` | 用户账号、资料、角色、状态和信任分 |
| `Activity` | `activity` | 线下活动主体 |
| `Registration` | `registration` | 用户报名活动记录 |
| `ActivityFavorite` | `activity_favorite` | 用户收藏活动 |
| `Circle` | `circle` | 同好圈 |
| `CircleMember` | `circle_member` | 用户加入圈子的成员关系 |
| `Post` | `post` | 圈子帖子 |
| `PostImage` | `post_image` | 帖子图片 |
| `Comment` | `comment` | 活动或帖子评论，支持楼中楼 |
| `CommentImage` | `comment_image` | 评论图片 |
| `Interaction` | `interaction` | 点赞、收藏、分享等互动记录 |
| `Review` | `review` | 旧版活动单项评分 |
| `ActivityReview` | `activity_review` | 活动多维评分 |
| `UserReview` | `user_review` | 活动参与者互评 |
| `TrustScoreLog` | `trust_score_log` | 用户信任分变更记录 |
| `ProfileVisibility` | `profile_visibility` | 用户主页可见性设置 |
| `UserFollow` | `user_follow` | 用户关注关系 |
| `DirectMessage` | `direct_message` | 私信消息 |
| `DirectMessageConversationState` | `direct_message_conversation_state` | 私信会话在单个用户侧的隐藏、删除、清空状态 |
| `Notification` | `notification` | 站内通知 |
| `EmailVerificationCode` | `email_verification_code` | 邮箱验证码 |
| `MerchantVerification` | `merchant_verification` | 商家认证申请和审核 |
| `AdminLog` | `admin_log` | 管理员操作日志 |

## User

表名：`user`

业务含义：保存用户账号、登录凭据、个人资料、角色、状态、信任分和定位偏好。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 用户 ID |
| `username` | String(80) | 否 | 无 | Unique | 登录用户名 |
| `nickname` | String(80) | 是 | 无 |  | 昵称 |
| `email` | String(120) | 否 | 无 | Unique | 邮箱 |
| `email_verified_at` | DateTime | 是 | 无 |  | 邮箱验证时间 |
| `password` | String(255) | 否 | 无 |  | 密码哈希，模型属性名为 `password_hash` |
| `avatar` | String(255) | 是 | 无 |  | 头像路径或 URL |
| `bio` | Text | 是 | 无 |  | 个人简介 |
| `interests` | Text | 是 | 无 |  | 兴趣标签文本 |
| `city` | String(80) | 是 | 无 |  | 用户填写城市 |
| `nearby_enabled` | Boolean | 否 | `False` |  | 附近的人开关 |
| `detected_city` | String(80) | 是 | 无 |  | 粗略定位城市 |
| `detected_region` | String(80) | 是 | 无 |  | 粗略定位地区 |
| `last_location_detected_at` | DateTime | 是 | 无 |  | 最近定位时间 |
| `last_ip` | String(45) | 是 | 无 |  | 最近 IP |
| `role` | String(20) | 否 | `user` |  | 用户角色，如 user、admin、merchant |
| `trust_score` | Integer | 否 | `100` |  | 信任分 |
| `status` | String(20) | 否 | `active` |  | 账号状态 |
| `banned_at` | DateTime | 是 | 无 |  | 封禁时间 |
| `deleted_at` | DateTime | 是 | 无 |  | 注销时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：一名用户可以创建多个活动、报名多个活动、收藏多个活动、发布多个帖子和评论、发送或接收私信、关注或被关注、提交评分、接收通知、提交商家认证、拥有主页可见性配置。

## Activity

表名：`activity`

业务含义：线下活动主体，保存活动内容、时间地点、人数、费用、标签、状态和组织者。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 活动 ID |
| `title` | String(120) | 否 | 无 |  | 活动标题 |
| `description` | Text | 是 | 无 |  | 简短介绍 |
| `detail` | Text | 是 | 无 |  | 详细介绍 |
| `city` | String(80) | 是 | 无 |  | 城市 |
| `location` | String(255) | 是 | 无 |  | 地点 |
| `start_time` | DateTime | 是 | 无 |  | 开始时间 |
| `end_time` | DateTime | 是 | 无 |  | 结束时间 |
| `timezone` | String(80) | 否 | `Asia/Shanghai` |  | 时区 |
| `max_participants` | Integer | 是 | 无 |  | 人数上限 |
| `initial_participants` | Integer | 否 | `0` |  | 初始参与人数 |
| `image` | String(255) | 是 | 无 |  | 活动图片 |
| `fee` | Float | 否 | `0` |  | 活动费用 |
| `tags` | Text | 是 | 无 |  | 兴趣标签 |
| `circle_id` | Integer | 是 | 无 | FK -> `circle.id` | 关联同好圈 |
| `status` | String(20) | 否 | `open` |  | 活动状态 |
| `cancel_reason` | Text | 是 | 无 |  | 取消原因 |
| `cancelled_at` | DateTime | 是 | 无 |  | 取消时间 |
| `is_featured` | Boolean | 否 | `False` |  | 是否精选 |
| `is_official` | Boolean | 否 | `False` |  | 是否官方活动 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `organizer_id` | Integer | 否 | 无 | FK -> `user.id` | 组织者 |
| `preparation` | Text | 是 | 无 |  | 准备事项 |

关系：一个活动属于一个组织者，可选关联一个圈子；一个活动可以有多条报名、收藏、评论、旧版评分、活动多维评分和用户互评。

## Registration

表名：`registration`

业务含义：连接用户和活动，记录报名或取消状态。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 报名 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 报名用户 |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 被报名活动 |
| `status` | String(20) | 否 | `registered` |  | 报名状态 |
| `cancel_reason` | Text | 是 | 无 |  | 取消原因 |
| `cancelled_at` | DateTime | 是 | 无 |  | 取消时间 |
| `register_time` | DateTime | 否 | `datetime.utcnow` |  | 报名时间 |

关系：多条报名属于一个用户，多条报名属于一个活动。当前模型没有数据库级 `user_id + activity_id` 唯一约束，重复报名主要由路由逻辑控制。

## ActivityFavorite

表名：`activity_favorite`

业务含义：用户收藏活动。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 收藏 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 收藏用户 |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 被收藏活动 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 收藏时间 |

约束：`user_id + activity_id` 唯一，避免重复收藏。

## Circle

表名：`circle`

业务含义：同好圈主体。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 圈子 ID |
| `name` | String(120) | 否 | 无 |  | 圈子名称 |
| `tag` | String(50) | 是 | 无 |  | 圈子标签 |
| `cover_image` | String(255) | 是 | 无 |  | 封面图 |
| `description` | Text | 是 | 无 |  | 简介 |
| `announcement` | Text | 是 | 无 |  | 公告 |
| `owner_id` | Integer | 是 | 无 | FK -> `user.id` | 圈主 |
| `pinned_post_id` | Integer | 是 | 无 | FK -> `post.id` | 置顶帖子 |
| `is_pinned` | Boolean | 否 | `False` |  | 是否置顶圈子 |
| `pinned_at` | DateTime | 是 | 无 |  | 置顶时间 |
| `is_system` | Boolean | 否 | `False` |  | 是否系统圈子 |
| `initial_member_count` | Integer | 否 | `0` |  | 初始成员数 |
| `member_count` | Integer | 否 | `0` |  | 成员数缓存 |
| `status` | String(20) | 否 | `active` |  | 圈子状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

关系：一个圈子有多个成员、帖子和活动；可有一个圈主和一个置顶帖子。

## CircleMember

表名：`circle_member`

业务含义：用户与圈子的成员关系。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 成员记录 ID |
| `circle_id` | Integer | 否 | 无 | FK -> `circle.id` | 圈子 |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 成员用户 |
| `role` | String(20) | 否 | `member` |  | 成员角色 |
| `status` | String(20) | 否 | `active` |  | 成员状态 |
| `joined_at` | DateTime | 否 | `datetime.utcnow` |  | 加入时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

约束：`circle_id + user_id` 唯一，避免重复加入同一圈子。

## Post

表名：`post`

业务含义：圈子帖子。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 帖子 ID |
| `title` | String(200) | 否 | 无 |  | 标题 |
| `content` | Text | 否 | 无 |  | 内容 |
| `type` | String(20) | 否 | `share` |  | 帖子类型 |
| `status` | String(20) | 否 | `published` |  | 帖子状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 作者 |
| `circle_id` | Integer | 否 | 无 | FK -> `circle.id` | 所属圈子 |

关系：帖子属于一个用户和一个圈子；帖子可以有多张图片和多条评论。

## PostImage

表名：`post_image`

业务含义：帖子图片。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 图片 ID |
| `post_id` | Integer | 否 | 无 | FK -> `post.id` | 所属帖子 |
| `image_path` | String(255) | 否 | 无 |  | 图片路径 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 上传时间 |

## Comment

表名：`comment`

业务含义：评论，可指向活动或帖子，并支持父评论形成楼中楼。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 评论 ID |
| `author_id` | Integer | 否 | 无 | FK -> `user.id` | 作者 |
| `activity_id` | Integer | 是 | 无 | FK -> `activity.id` | 目标活动 |
| `post_id` | Integer | 是 | 无 | FK -> `post.id` | 目标帖子 |
| `parent_id` | Integer | 是 | 无 | FK -> `comment.id` | 父评论 |
| `content` | Text | 否 | 无 |  | 评论内容 |
| `status` | String(20) | 否 | `published` |  | 评论状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

约束：`activity_id` 和 `post_id` 必须且只能有一个不为空。

## CommentImage

表名：`comment_image`

业务含义：评论图片。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 图片 ID |
| `comment_id` | Integer | 否 | 无 | FK -> `comment.id` | 所属评论 |
| `image_path` | String(255) | 否 | 无 |  | 图片路径 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 上传时间 |

## Interaction

表名：`interaction`

业务含义：记录用户对帖子、评论等目标的互动。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 互动 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 操作用户 |
| `target_type` | String(30) | 否 | 无 |  | 目标类型 |
| `target_id` | Integer | 否 | 无 |  | 目标 ID |
| `action_type` | String(20) | 否 | 无 |  | 动作类型 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

约束：`user_id + target_type + target_id + action_type` 唯一，避免重复同类互动。

## Review

表名：`review`

业务含义：旧版活动单项评分，保留用于兼容。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 评分 ID |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 被评分活动 |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 评分用户 |
| `rating` | Integer | 否 | 无 |  | 单项评分 |
| `comment` | Text | 是 | 无 |  | 文字评价 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

## ActivityReview

表名：`activity_review`

业务含义：当前更完整的活动多维评分。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 活动评分 ID |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 被评分活动 |
| `reviewer_id` | Integer | 否 | 无 | FK -> `user.id` | 评分用户 |
| `organization_score` | Integer | 否 | 无 |  | 组织评分 |
| `venue_score` | Integer | 否 | 无 |  | 场地评分 |
| `content_score` | Integer | 否 | 无 |  | 内容评分 |
| `value_score` | Integer | 否 | 无 |  | 价值评分 |
| `experience_score` | Integer | 否 | 无 |  | 体验评分 |
| `average_score` | Float | 否 | 无 |  | 平均分 |
| `comment` | Text | 是 | 无 |  | 文字评价 |
| `status` | String(20) | 否 | `published` |  | 评价状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

约束：`activity_id + reviewer_id` 唯一，防止同一用户重复评价同一活动。

## UserReview

表名：`user_review`

业务含义：活动参与者之间的互评。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 用户互评 ID |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 关联活动 |
| `reviewer_id` | Integer | 否 | 无 | FK -> `user.id` | 评价者 |
| `reviewee_id` | Integer | 否 | 无 | FK -> `user.id` | 被评价者 |
| `punctuality_score` | Integer | 否 | 无 |  | 准时评分 |
| `friendliness_score` | Integer | 否 | 无 |  | 友善评分 |
| `communication_score` | Integer | 否 | 无 |  | 沟通评分 |
| `reliability_score` | Integer | 否 | 无 |  | 可靠评分 |
| `respect_score` | Integer | 否 | 无 |  | 尊重评分 |
| `safety_score` | Integer | 否 | 无 |  | 安全评分 |
| `average_score` | Float | 否 | 无 |  | 平均分 |
| `comment` | Text | 是 | 无 |  | 文字评价 |
| `status` | String(20) | 否 | `published` |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

约束：`activity_id + reviewer_id + reviewee_id` 唯一；六个维度评分均限制在 1 到 5。

## TrustScoreLog

表名：`trust_score_log`

业务含义：记录用户信任分变化。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 日志 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 被影响用户 |
| `changed_by_id` | Integer | 是 | 无 | FK -> `user.id` | 操作者 |
| `change_type` | String(50) | 否 | 无 |  | 变化类型 |
| `delta` | Integer | 否 | 无 |  | 分数变化 |
| `score_before` | Integer | 否 | 无 |  | 变化前分数 |
| `score_after` | Integer | 否 | 无 |  | 变化后分数 |
| `reason` | Text | 是 | 无 |  | 原因 |
| `related_type` | String(50) | 是 | 无 |  | 关联对象类型 |
| `related_id` | Integer | 是 | 无 |  | 关联对象 ID |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

## ProfileVisibility

表名：`profile_visibility`

业务含义：用户主页可见性配置。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 配置 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 用户 |
| `profile_scope` | String(20) | 否 | `public` |  | 主页可见范围 |
| `activity_scope` | String(20) | 否 | `public` |  | 活动可见范围 |
| `circle_scope` | String(20) | 否 | `public` |  | 圈子可见范围 |
| `review_scope` | String(20) | 否 | `members` |  | 评价可见范围 |
| `trust_score_scope` | String(20) | 否 | `private` |  | 信任分可见范围 |
| `show_interests` | Boolean | 否 | `True` |  | 是否展示兴趣 |
| `show_interactions` | Boolean | 否 | `True` |  | 是否展示互动 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

约束：`user_id` 唯一，即一个用户一份配置。

## UserFollow

表名：`user_follow`

业务含义：用户关注关系。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 关注记录 ID |
| `follower_id` | Integer | 否 | 无 | FK -> `user.id` | 关注者 |
| `followed_id` | Integer | 否 | 无 | FK -> `user.id` | 被关注者 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 关注时间 |

约束：`follower_id + followed_id` 唯一；`follower_id != followed_id`。

## DirectMessage

表名：`direct_message`

业务含义：私信消息。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 消息 ID |
| `sender_id` | Integer | 否 | 无 | FK -> `user.id` | 发送者 |
| `recipient_id` | Integer | 否 | 无 | FK -> `user.id` | 接收者 |
| `content` | Text | 是 | 无 |  | 文本内容 |
| `message_type` | String(20) | 否 | `text` |  | 消息类型 |
| `image_path` | String(255) | 是 | 无 |  | 图片路径 |
| `read_at` | DateTime | 是 | 无 |  | 已读时间 |
| `expires_at` | DateTime | 否 | 无 |  | 过期时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

## DirectMessageConversationState

表名：`direct_message_conversation_state`

业务含义：记录某个用户视角下与另一个用户的会话隐藏、删除和清空状态。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 会话状态 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 当前用户 |
| `other_user_id` | Integer | 否 | 无 | FK -> `user.id` | 对方用户 |
| `is_hidden` | Boolean | 否 | `False` |  | 是否隐藏 |
| `hidden_at` | DateTime | 是 | 无 |  | 隐藏时间 |
| `is_deleted` | Boolean | 否 | `False` |  | 是否删除 |
| `deleted_at` | DateTime | 是 | 无 |  | 删除时间 |
| `cleared_at` | DateTime | 是 | 无 |  | 清空历史时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

约束：`user_id + other_user_id` 唯一；`user_id != other_user_id`。

## Notification

表名：`notification`

业务含义：站内通知。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 通知 ID |
| `recipient_id` | Integer | 否 | 无 | FK -> `user.id` | 接收者 |
| `type` | String(50) | 否 | 无 |  | 通知类型 |
| `title` | String(120) | 否 | 无 |  | 标题 |
| `content` | Text | 是 | 无 |  | 内容 |
| `related_type` | String(50) | 是 | 无 |  | 关联对象类型 |
| `related_id` | Integer | 是 | 无 |  | 关联对象 ID |
| `read_at` | DateTime | 是 | 无 |  | 已读时间 |
| `expires_at` | DateTime | 否 | 无 |  | 过期时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

## EmailVerificationCode

表名：`email_verification_code`

业务含义：注册、修改邮箱、修改密码、找回密码等场景的邮箱验证码。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 验证码 ID |
| `user_id` | Integer | 是 | 无 | FK -> `user.id` | 关联用户 |
| `email` | String(120) | 否 | 无 | Index | 邮箱 |
| `code` | String(128) | 否 | 无 |  | 验证码或哈希 |
| `purpose` | String(30) | 否 | `register` |  | 用途 |
| `expires_at` | DateTime | 否 | 无 |  | 过期时间 |
| `used_at` | DateTime | 是 | 无 |  | 使用时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

## MerchantVerification

表名：`merchant_verification`

业务含义：商家认证申请和管理员审核。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 认证 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 申请用户 |
| `business_name` | String(120) | 否 | 无 |  | 商家名称 |
| `license_number` | String(120) | 是 | 无 |  | 证照编号 |
| `document_path` | String(255) | 是 | 无 |  | 证照文件路径 |
| `reason` | Text | 是 | 无 |  | 申请说明 |
| `contact` | String(160) | 是 | 无 |  | 联系方式 |
| `status` | String(20) | 否 | `pending` |  | 审核状态 |
| `reject_reason` | Text | 是 | 无 |  | 驳回原因 |
| `reviewer_id` | Integer | 是 | 无 | FK -> `user.id` | 审核管理员 |
| `reviewed_at` | DateTime | 是 | 无 |  | 审核时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow` |  | 更新时间 |

## AdminLog

表名：`admin_log`

业务含义：记录管理员操作。

| 字段名 | 类型 | 可为空 | 默认值 | 主键 / 外键 | 业务含义 |
|---|---|---|---|---|---|
| `id` | Integer | 否 | 无 | PK | 日志 ID |
| `admin_id` | Integer | 否 | 无 | FK -> `user.id` | 管理员 |
| `action` | String(80) | 否 | 无 |  | 操作名称 |
| `target_type` | String(50) | 否 | 无 |  | 目标类型 |
| `target_id` | Integer | 是 | 无 |  | 目标 ID |
| `detail` | Text | 是 | 无 |  | 详细说明 |
| `ip_address` | String(45) | 是 | 无 |  | 操作 IP |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

## 当前未实现或需澄清的数据结构

| 预期名称 | 当前代码状态 |
|---|---|
| `Rating` | 当前没有名为 `Rating` 的模型。评分由 `Review`、`ActivityReview` 和 `UserReview` 实现。 |
| 独立 `Tag` 表 | 当前没有独立标签表。活动使用 `Activity.tags` 文本字段，圈子使用 `Circle.tag` 字符串字段。 |
| 独立 `Location` 表 | 当前没有独立地点表。活动地点保存在 `Activity.city` 和 `Activity.location` 中。 |
| 活动报名唯一约束 | `Registration` 当前没有数据库级 `user_id + activity_id` 唯一约束，重复报名由业务逻辑控制。 |

## 约束和索引要点

- `User.username` 唯一。
- `User.email` 唯一。
- `ActivityFavorite.user_id + activity_id` 唯一。
- `ActivityReview.activity_id + reviewer_id` 唯一。
- `UserReview.activity_id + reviewer_id + reviewee_id` 唯一。
- `CircleMember.circle_id + user_id` 唯一。
- `Interaction.user_id + target_type + target_id + action_type` 唯一。
- `ProfileVisibility.user_id` 唯一。
- `UserFollow.follower_id + followed_id` 唯一，且不能关注自己。
- `DirectMessageConversationState.user_id + other_user_id` 唯一，且不能与自己形成会话。
- `Comment` 通过检查约束要求评论目标必须是活动或帖子之一。
