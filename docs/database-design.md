# 数据库设计

最后更新：2026-06-05

本文以当前 `app/models.py` 为准，说明 Gatherly Web 当前真实 SQLAlchemy 数据库模型。当前正式数据库是 Neon PostgreSQL；SQLite 只是在未设置 `DATABASE_URL` 时的本地开发 fallback，不是生产数据库。

ER 图见：[er-diagram.md](er-diagram.md)。

## 当前数据库架构

| 项目 | 当前方案 |
|---|---|
| 正式数据库 | Neon PostgreSQL |
| 本地开发数据库 | 未设置 `DATABASE_URL` 时 fallback 到 SQLite |
| ORM | Flask-SQLAlchemy |
| 迁移工具 | Flask-Migrate / Alembic |
| 模型定义 | `app/models.py` |
| 迁移目录 | `migrations/` |
| 生产运行 | Render Web Service, `gunicorn wsgi:app` |
| 对象存储 | Cloudflare R2 |
| 代码与文档 | GitHub |

Render 负责运行 Flask Web 服务，不作为持久化文件或数据库存储。Neon PostgreSQL 保存用户、活动、圈子、帖子、评论、私信、通知、后台管理、商家认证、用户反馈等关系型数据。Cloudflare R2 保存用户上传图片和认证材料文件本体。GitHub 只保存代码、文档、静态资源、脚本和 migrations，不保存真实用户数据、密钥、数据库备份或图片备份。

生产 schema 来源是 `migrations/`。`ensure_*_schema()` helper 仅用于 SQLite 本地 fallback 或历史兼容；在 Render / Neon PostgreSQL 上不应自动建表、补列或创建索引。生产环境不应依赖 `db.create_all()` 作为正式建表或改表方式。

## Neon PostgreSQL 与本地开发数据库

| 维度 | Neon PostgreSQL | 本地 SQLite fallback |
|---|---|---|
| 用途 | 正式线上关系型数据库 | 本地快速开发或演示 |
| 触发条件 | 设置 `DATABASE_URL` | 未设置 `DATABASE_URL` |
| schema 变更 | 必须通过 Alembic migration 和 `flask db upgrade` | 可由 migration 或 SQLite 兼容 helper 辅助补齐 |
| 连接 URL | Render 运行时通常用 pooled URL；迁移维护用 direct URL | Flask instance 目录下的本地数据库文件 |
| 数据安全 | 真实用户数据，只保存在 Neon | 不应承载生产数据 |

修改 `app/models.py` 后必须使用 Flask-Migrate 生成 migration。正式 Neon 数据库升级需要执行 `flask db upgrade`。本次文档更新不应生成新的 migration，也不应执行 `flask db migrate` 或 `flask db upgrade`。

## R2 与数据库的关系

Cloudflare R2 保存图片和认证材料文件本体，数据库只保存可访问 URL 或历史本地 fallback 路径。生产语义下，下列字段应保存 R2 public URL，不保存文件二进制内容。

| 字段 | 含义 |
|---|---|
| `User.avatar` | 用户头像 URL |
| `Activity.image` | 活动图片 URL |
| `Circle.cover_image` | 圈子封面 URL |
| `PostImage.image_url` | 帖子图片 URL |
| `CommentImage.image_url` | 评论图片 URL |
| `DirectMessage.image_url` | 私信图片 URL |
| `MerchantVerification.document_url` | 商家认证材料 URL |

未配置 R2 的非生产环境可能保存 `/static/uploads/...` 本地 fallback 路径；这只用于本地开发或历史迁移来源，不是当前正式图片存储方案。

## 自检发现

| 检查项 | 结果 |
|---|---|
| 正式架构 | 当前正式方案统一为 Render + Neon PostgreSQL + Cloudflare R2 + GitHub。 |
| SQLite | 只应描述为本地开发 fallback，不是线上正式数据库。 |
| 本地 uploads | 只应描述为本地 fallback 或历史迁移来源，不是线上正式图片存储。 |
| PythonAnywhere | 只应出现在归档或历史方案说明中，不是当前部署方案。 |
| `UserReview` | 当前 `app/models.py` 没有 `UserReview` 模型。迁移 `52ce70c39825_initial_schema.py` 曾创建 `user_review`，后续 `d8a74b60405f_add_circle_ratings_and_remove_user_.py` 已删除该表并新增 `circle_rating`。当前模型与迁移链在这一点上没有发现不一致。 |
| 当前模型清单 | 以本文件下方 24 个 SQLAlchemy Model 为准。 |

## 当前所有 SQLAlchemy Model

| Model | 表名 | 业务含义 |
|---|---|---|
| `User` | `user` | 用户、管理员和商家账号基础资料。 |
| `Activity` | `activity` | 活动主体。 |
| `Registration` | `registration` | 活动报名记录。 |
| `EmailVerificationCode` | `email_verification_code` | 邮箱验证码。 |
| `Notification` | `notification` | 站内通知。 |
| `Feedback` | `feedback` | 用户反馈与管理员回复。 |
| `DirectMessage` | `direct_message` | 私信消息。 |
| `DirectMessageConversationState` | `direct_message_conversation_state` | 用户侧私信会话隐藏、删除和清空状态。 |
| `UserFollow` | `user_follow` | 用户关注关系。 |
| `MerchantVerification` | `merchant_verification` | 商家认证申请和审核记录。 |
| `ActivityFavorite` | `activity_favorite` | 活动收藏记录。 |
| `Circle` | `circle` | 同好圈。 |
| `Post` | `post` | 圈子帖子。 |
| `PostImage` | `post_image` | 帖子图片 URL 记录。 |
| `ActivityReview` | `activity_review` | 活动多维评分。 |
| `CircleRating` | `circle_rating` | 同好圈评分。 |
| `TrustScoreLog` | `trust_score_log` | 用户信任分变更日志。 |
| `CircleMember` | `circle_member` | 圈子成员关系。 |
| `Comment` | `comment` | 活动或帖子评论，支持回复。 |
| `CommentImage` | `comment_image` | 评论图片 URL 记录。 |
| `Interaction` | `interaction` | 通用互动记录。 |
| `ProfileVisibility` | `profile_visibility` | 用户主页可见性设置。 |
| `AdminLog` | `admin_log` | 管理员操作日志。 |
| `Review` | `review` | 旧版活动单项评分兼容表。 |

当前没有名为 `Rating` 或 `UserReview` 的 SQLAlchemy Model。活动评分由 `Review` 和 `ActivityReview` 承担；圈子评分由 `CircleRating` 承担。

## 字段定义

表格中的“唯一 / 索引”只记录当前 `app/models.py` 中声明的 `unique=True`、`index=True`、`UniqueConstraint` 和主要检查约束；部分 SQLite 兼容 helper 运行时创建的历史索引不作为正式 PostgreSQL schema 设计来源。

### User / `user`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 用户 ID |
| `username` | String(80) | 否 | 无 | Unique |  | 登录用户名 |
| `nickname` | String(80) | 是 | 无 |  |  | 昵称 |
| `email` | String(120) | 否 | 无 | Unique |  | 邮箱 |
| `email_verified_at` | DateTime | 是 | 无 |  |  | 邮箱验证时间 |
| `password` | String(255) | 否 | 无 |  |  | 密码哈希，模型属性名为 `password_hash` |
| `avatar` | String(255) | 是 | 无 |  |  | 头像 URL |
| `bio` | Text | 是 | 无 |  |  | 个人简介 |
| `interests` | Text | 是 | 无 |  |  | 兴趣文本 |
| `city` | String(80) | 是 | 无 |  |  | 用户填写城市 |
| `nearby_enabled` | Boolean | 否 | `False` |  |  | 附近的人开关 |
| `detected_city` | String(80) | 是 | 无 |  |  | 粗略定位城市 |
| `detected_region` | String(80) | 是 | 无 |  |  | 粗略定位地区 |
| `last_location_detected_at` | DateTime | 是 | 无 |  |  | 最近定位时间 |
| `last_ip` | String(45) | 是 | 无 |  |  | 最近 IP |
| `role` | String(20) | 否 | `user` |  |  | 角色 |
| `trust_score` | Integer | 否 | `100` |  |  | 信任分 |
| `status` | String(20) | 否 | `active` |  |  | 账号状态 |
| `banned_at` | DateTime | 是 | 无 |  |  | 封禁时间 |
| `deleted_at` | DateTime | 是 | 无 |  |  | 注销时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### Activity / `activity`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 活动 ID |
| `title` | String(120) | 否 | 无 |  |  | 标题 |
| `description` | Text | 是 | 无 |  |  | 简介 |
| `detail` | Text | 是 | 无 |  |  | 详情 |
| `city` | String(80) | 是 | 无 |  |  | 城市 |
| `location` | String(255) | 是 | 无 |  |  | 地点 |
| `start_time` | DateTime | 是 | 无 |  |  | 开始时间 |
| `end_time` | DateTime | 是 | 无 |  |  | 结束时间 |
| `timezone` | String(80) | 否 | `Asia/Shanghai` |  |  | 时区 |
| `max_participants` | Integer | 是 | 无 |  |  | 人数上限 |
| `initial_participants` | Integer | 否 | `0` |  |  | 初始参与数 |
| `image` | String(255) | 是 | 无 |  |  | 活动图片 URL |
| `fee` | Float | 否 | `0` |  |  | 费用 |
| `tags` | Text | 是 | 无 |  |  | 标签文本 |
| `circle_id` | Integer | 是 | 无 |  | `circle.id` | 所属圈子 |
| `status` | String(20) | 否 | `open` |  |  | 状态 |
| `cancel_reason` | Text | 是 | 无 |  |  | 取消原因 |
| `cancelled_at` | DateTime | 是 | 无 |  |  | 取消时间 |
| `is_featured` | Boolean | 否 | `False` |  |  | 是否精选 |
| `is_official` | Boolean | 否 | `False` |  |  | 是否官方 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `organizer_id` | Integer | 否 | 无 |  | `user.id` | 组织者 |
| `preparation` | Text | 是 | 无 |  |  | 活动准备事项 |

### Registration / `registration`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 报名 ID |
| `user_id` | Integer | 否 | 无 | Unique(`user_id`, `activity_id`) | `user.id` | 报名用户 |
| `activity_id` | Integer | 否 | 无 | Unique(`user_id`, `activity_id`) | `activity.id` | 被报名活动 |
| `status` | String(20) | 否 | `registered` |  |  | 报名状态 |
| `cancel_reason` | Text | 是 | 无 |  |  | 取消原因 |
| `cancelled_at` | DateTime | 是 | 无 |  |  | 取消时间 |
| `register_time` | DateTime | 否 | `datetime.utcnow` |  |  | 报名时间 |

### EmailVerificationCode / `email_verification_code`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 验证码 ID |
| `user_id` | Integer | 是 | 无 |  | `user.id` | 关联用户 |
| `email` | String(120) | 否 | 无 | Index |  | 邮箱 |
| `code` | String(128) | 否 | 无 |  |  | 验证码或哈希 |
| `purpose` | String(30) | 否 | `register` |  |  | 用途 |
| `expires_at` | DateTime | 否 | 无 |  |  | 过期时间 |
| `used_at` | DateTime | 是 | 无 |  |  | 使用时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### Notification / `notification`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 通知 ID |
| `recipient_id` | Integer | 否 | 无 | Index | `user.id` | 接收用户 |
| `type` | String(50) | 否 | 无 |  |  | 通知类型 |
| `title` | String(120) | 否 | 无 |  |  | 标题 |
| `content` | Text | 是 | 无 |  |  | 内容 |
| `related_type` | String(50) | 是 | 无 |  |  | 关联对象类型，非外键 |
| `related_id` | Integer | 是 | 无 |  |  | 关联对象 ID，非外键 |
| `read_at` | DateTime | 是 | 无 | Index |  | 已读时间 |
| `expires_at` | DateTime | 否 | 无 | Index |  | 过期时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### Feedback / `feedback`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 反馈 ID |
| `user_id` | Integer | 否 | 无 | Index | `user.id` | 提交用户 |
| `category` | String(50) | 否 | 无 |  |  | 反馈分类 |
| `title` | String(120) | 否 | 无 |  |  | 标题 |
| `content` | Text | 否 | 无 |  |  | 反馈内容 |
| `status` | String(20) | 否 | `open` | Index |  | 处理状态 |
| `admin_reply` | Text | 是 | 无 |  |  | 管理员回复 |
| `replied_by_id` | Integer | 是 | 无 | Index | `user.id` | 回复管理员 |
| `replied_at` | DateTime | 是 | 无 |  |  | 回复时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` | Index |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

### DirectMessage / `direct_message`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 私信 ID |
| `sender_id` | Integer | 否 | 无 |  | `user.id` | 发送用户 |
| `recipient_id` | Integer | 否 | 无 |  | `user.id` | 接收用户 |
| `content` | Text | 是 | 无 |  |  | 文本内容 |
| `message_type` | String(20) | 否 | `text` |  |  | 消息类型 |
| `image_url` | String(255) | 是 | 无 |  |  | 图片 URL |
| `read_at` | DateTime | 是 | 无 | Index |  | 已读时间 |
| `expires_at` | DateTime | 否 | 无 | Index |  | 过期时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### DirectMessageConversationState / `direct_message_conversation_state`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 会话状态 ID |
| `user_id` | Integer | 否 | 无 | Index; Unique(`user_id`, `other_user_id`) | `user.id` | 当前用户 |
| `other_user_id` | Integer | 否 | 无 | Index; Unique(`user_id`, `other_user_id`) | `user.id` | 对方用户 |
| `is_hidden` | Boolean | 否 | `False` |  |  | 是否隐藏 |
| `hidden_at` | DateTime | 是 | 无 |  |  | 隐藏时间 |
| `is_deleted` | Boolean | 否 | `False` |  |  | 是否删除 |
| `deleted_at` | DateTime | 是 | 无 |  |  | 删除时间 |
| `cleared_at` | DateTime | 是 | 无 |  |  | 清空时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

检查约束：`ck_direct_message_conversation_state_not_self` 禁止自己与自己形成会话状态。

### UserFollow / `user_follow`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 关注记录 ID |
| `follower_id` | Integer | 否 | 无 | Index; Unique(`follower_id`, `followed_id`) | `user.id` | 关注者 |
| `followed_id` | Integer | 否 | 无 | Index; Unique(`follower_id`, `followed_id`) | `user.id` | 被关注者 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

检查约束：`ck_user_follow_not_self` 禁止关注自己。

### MerchantVerification / `merchant_verification`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 认证 ID |
| `user_id` | Integer | 否 | 无 |  | `user.id` | 申请用户 |
| `business_name` | String(120) | 否 | 无 |  |  | 商家名称 |
| `license_number` | String(120) | 是 | 无 |  |  | 证照编号 |
| `document_url` | String(255) | 是 | 无 |  |  | 认证材料 URL |
| `reason` | Text | 是 | 无 |  |  | 申请说明 |
| `contact` | String(160) | 是 | 无 |  |  | 联系方式 |
| `status` | String(20) | 否 | `pending` |  |  | 审核状态 |
| `reject_reason` | Text | 是 | 无 |  |  | 驳回原因 |
| `reviewer_id` | Integer | 是 | 无 |  | `user.id` | 审核管理员 |
| `reviewed_at` | DateTime | 是 | 无 |  |  | 审核时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

### ActivityFavorite / `activity_favorite`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 收藏 ID |
| `user_id` | Integer | 否 | 无 | Unique(`user_id`, `activity_id`) | `user.id` | 收藏用户 |
| `activity_id` | Integer | 否 | 无 | Unique(`user_id`, `activity_id`) | `activity.id` | 被收藏活动 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 收藏时间 |

### Circle / `circle`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 圈子 ID |
| `name` | String(120) | 否 | 无 |  |  | 名称 |
| `tag` | String(50) | 是 | 无 |  |  | 标签 |
| `cover_image` | String(255) | 是 | 无 |  |  | 封面图片 URL |
| `description` | Text | 是 | 无 |  |  | 简介 |
| `announcement` | Text | 是 | 无 |  |  | 公告 |
| `owner_id` | Integer | 是 | 无 |  | `user.id` | 圈主 |
| `pinned_post_id` | Integer | 是 | 无 |  | `post.id` | 置顶帖子 |
| `is_pinned` | Boolean | 否 | `False` |  |  | 是否置顶圈子 |
| `pinned_at` | DateTime | 是 | 无 |  |  | 置顶时间 |
| `is_system` | Boolean | 否 | `False` |  |  | 是否系统圈子 |
| `initial_member_count` | Integer | 否 | `0` |  |  | 初始成员数 |
| `member_count` | Integer | 否 | `0` |  |  | 成员数缓存 |
| `status` | String(20) | 否 | `active` |  |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

### Post / `post`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 帖子 ID |
| `title` | String(200) | 否 | 无 |  |  | 标题 |
| `content` | Text | 否 | 无 |  |  | 内容 |
| `type` | String(20) | 否 | `share` |  |  | 类型 |
| `status` | String(20) | 否 | `published` |  |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `user_id` | Integer | 否 | 无 |  | `user.id` | 作者 |
| `circle_id` | Integer | 否 | 无 |  | `circle.id` | 所属圈子 |

### PostImage / `post_image`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 图片 ID |
| `post_id` | Integer | 否 | 无 |  | `post.id` | 所属帖子 |
| `image_url` | String(255) | 否 | 无 |  |  | 图片 URL |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### ActivityReview / `activity_review`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 活动评分 ID |
| `activity_id` | Integer | 否 | 无 | Unique(`activity_id`, `reviewer_id`) | `activity.id` | 活动 |
| `reviewer_id` | Integer | 否 | 无 | Unique(`activity_id`, `reviewer_id`) | `user.id` | 评分用户 |
| `organization_score` | Integer | 否 | 无 |  |  | 组织评分 |
| `venue_score` | Integer | 否 | 无 |  |  | 场地评分 |
| `content_score` | Integer | 否 | 无 |  |  | 内容评分 |
| `value_score` | Integer | 否 | 无 |  |  | 价值评分 |
| `experience_score` | Integer | 否 | 无 |  |  | 体验评分 |
| `average_score` | Float | 否 | 无 |  |  | 平均分 |
| `comment` | Text | 是 | 无 |  |  | 评价文字 |
| `status` | String(20) | 否 | `published` |  |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

### CircleRating / `circle_rating`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 圈子评分 ID |
| `circle_id` | Integer | 否 | 无 | Index; Unique(`circle_id`, `user_id`) | `circle.id` | 被评分圈子 |
| `user_id` | Integer | 否 | 无 | Index; Unique(`circle_id`, `user_id`) | `user.id` | 评分用户 |
| `rating` | Integer | 否 | 无 | Check 1-5 |  | 评分 |
| `comment` | Text | 是 | 无 |  |  | 评价文字 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

### TrustScoreLog / `trust_score_log`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 日志 ID |
| `user_id` | Integer | 否 | 无 |  | `user.id` | 被影响用户 |
| `changed_by_id` | Integer | 是 | 无 |  | `user.id` | 操作者 |
| `change_type` | String(50) | 否 | 无 |  |  | 变更类型 |
| `delta` | Integer | 否 | 无 |  |  | 分数变化 |
| `score_before` | Integer | 否 | 无 |  |  | 变更前分数 |
| `score_after` | Integer | 否 | 无 |  |  | 变更后分数 |
| `reason` | Text | 是 | 无 |  |  | 原因 |
| `related_type` | String(50) | 是 | 无 |  |  | 关联对象类型，非外键 |
| `related_id` | Integer | 是 | 无 |  |  | 关联对象 ID，非外键 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### CircleMember / `circle_member`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 成员记录 ID |
| `circle_id` | Integer | 否 | 无 | Unique(`circle_id`, `user_id`) | `circle.id` | 圈子 |
| `user_id` | Integer | 否 | 无 | Unique(`circle_id`, `user_id`) | `user.id` | 用户 |
| `role` | String(20) | 否 | `member` |  |  | 成员角色 |
| `status` | String(20) | 否 | `active` |  |  | 成员状态 |
| `joined_at` | DateTime | 否 | `datetime.utcnow` |  |  | 加入时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

### Comment / `comment`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 评论 ID |
| `author_id` | Integer | 否 | 无 |  | `user.id` | 作者 |
| `activity_id` | Integer | 是 | 无 | Check single target | `activity.id` | 目标活动 |
| `post_id` | Integer | 是 | 无 | Check single target | `post.id` | 目标帖子 |
| `parent_id` | Integer | 是 | 无 |  | `comment.id` | 父评论 |
| `content` | Text | 否 | 无 |  |  | 评论内容 |
| `status` | String(20) | 否 | `published` |  |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

检查约束：`ck_comment_single_target` 要求评论目标必须且只能是活动或帖子之一。

### CommentImage / `comment_image`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 图片 ID |
| `comment_id` | Integer | 否 | 无 |  | `comment.id` | 所属评论 |
| `image_url` | String(255) | 否 | 无 |  |  | 图片 URL |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### Interaction / `interaction`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 互动 ID |
| `user_id` | Integer | 否 | 无 | Unique(`user_id`, `target_type`, `target_id`, `action_type`) | `user.id` | 用户 |
| `target_type` | String(30) | 否 | 无 | Unique composite |  | 目标类型，非外键 |
| `target_id` | Integer | 否 | 无 | Unique composite |  | 目标 ID，非外键 |
| `action_type` | String(20) | 否 | 无 | Unique composite |  | 动作类型 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### ProfileVisibility / `profile_visibility`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 配置 ID |
| `user_id` | Integer | 否 | 无 | Unique | `user.id` | 用户 |
| `profile_scope` | String(20) | 否 | `public` |  |  | 主页可见范围 |
| `activity_scope` | String(20) | 否 | `public` |  |  | 活动可见范围 |
| `circle_scope` | String(20) | 否 | `public` |  |  | 圈子可见范围 |
| `review_scope` | String(20) | 否 | `members` |  |  | 评价可见范围 |
| `trust_score_scope` | String(20) | 否 | `private` |  |  | 信任分可见范围 |
| `show_interests` | Boolean | 否 | `True` |  |  | 是否展示兴趣 |
| `show_interactions` | Boolean | 否 | `True` |  |  | 是否展示互动 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  |  | 更新时间 |

### AdminLog / `admin_log`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 日志 ID |
| `admin_id` | Integer | 否 | 无 |  | `user.id` | 管理员 |
| `action` | String(80) | 否 | 无 |  |  | 操作名 |
| `target_type` | String(50) | 否 | 无 |  |  | 目标类型 |
| `target_id` | Integer | 是 | 无 |  |  | 目标 ID |
| `detail` | Text | 是 | 无 |  |  | 详情 |
| `ip_address` | String(45) | 是 | 无 |  |  | IP 地址 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

### Review / `review`

| 字段名 | 类型 | 可为空 | 默认值 | 唯一 / 索引 | 外键关系 | 业务含义 |
|---|---|---:|---|---|---|---|
| `id` | Integer | 否 | 无 | PK |  | 旧版评分 ID |
| `activity_id` | Integer | 否 | 无 |  | `activity.id` | 活动 |
| `user_id` | Integer | 否 | 无 |  | `user.id` | 评分用户 |
| `rating` | Integer | 否 | 无 |  |  | 单项评分 |
| `comment` | Text | 是 | 无 |  |  | 评价文字 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  |  | 创建时间 |

## 主要业务关系

- 用户与活动：`User.id` 通过 `Activity.organizer_id` 关联到用户，一个用户可组织多个活动；活动可选通过 `Activity.circle_id` 关联到一个同好圈。
- 用户与报名：`Registration` 连接用户和活动，`uq_registration_user_activity` 防止同一用户重复报名同一活动。
- 用户与活动收藏：`ActivityFavorite` 连接用户和活动，`uq_activity_favorite_user_activity` 防止重复收藏。
- 用户与同好圈：`Circle.owner_id` 表示圈主；`CircleMember` 连接用户和圈子，`uq_circle_member_circle_user` 防止重复加入记录。
- 同好圈与帖子：`Post.circle_id` 表示帖子所属圈子；`Circle.pinned_post_id` 可指向一个置顶帖子。
- 帖子与评论：`Comment.post_id` 指向帖子；评论也可通过 `parent_id` 指向父评论形成回复。
- 活动与评论：`Comment.activity_id` 指向活动；`ck_comment_single_target` 保证一条评论只属于一个活动或一个帖子。
- 活动与评分：`Review` 是旧版单项活动评分；`ActivityReview` 是当前活动多维评分，`uq_activity_review_activity_reviewer` 防止同一用户重复评价同一活动。
- 同好圈与评分：`CircleRating` 连接圈子和用户，`uq_circle_rating_circle_user` 防止同一用户重复评价同一圈子，`ck_circle_rating_rating_range` 限制评分为 1-5。
- 私信：`DirectMessage.sender_id` 和 `recipient_id` 都关联 `User`；`DirectMessageConversationState` 保存某个用户视角下与另一个用户的会话隐藏、删除和清空状态。
- 通知：`Notification.recipient_id` 关联接收用户；`related_type` / `related_id` 是通用引用，不是数据库外键。
- 管理员日志：`AdminLog.admin_id` 关联执行操作的管理员用户；`target_type` / `target_id` 用于记录目标对象，不是数据库外键。
- 商家认证：`MerchantVerification.user_id` 关联申请用户，`reviewer_id` 可关联审核管理员，`document_url` 保存认证材料 URL。
- 用户反馈：`Feedback.user_id` 关联提交用户，`replied_by_id` 可关联回复管理员。
- 信任分日志：`TrustScoreLog.user_id` 关联被影响用户，`changed_by_id` 可关联操作者；`related_type` / `related_id` 是通用引用。
- 关注关系：`UserFollow.follower_id` 与 `followed_id` 都关联 `User`，唯一约束防止重复关注，检查约束防止关注自己。
- 资料可见性：`ProfileVisibility.user_id` 与用户一对一，唯一约束保证每个用户最多一份配置。

## 数据库迁移说明

数据库字段或关系变更必须单独评估，推荐单独 PR。

1. 修改 `app/models.py`。
2. 设置 Flask 入口：

   ```powershell
   $env:FLASK_APP='wsgi:app'
   ```

3. 设置 Neon Direct URL，不使用 pooled URL 执行迁移：

   ```powershell
   $env:DATABASE_URL='<Neon Direct URL, not the pooler URL>'
   ```

4. 生成 migration：

   ```powershell
   flask db migrate -m "describe schema change"
   ```

5. 审查生成的 `migrations/versions/*.py`，确认不会误删数据。
6. 对正式 Neon 数据库执行升级：

   ```powershell
   flask db upgrade
   ```

7. 提交 `app/models.py` 和对应 `migrations/`。

普通代码或文档改动不需要手动改 Neon 或 R2。只有数据库 schema 变化需要迁移；上传文件本体始终进入 R2，数据库只保存 URL。

本次文档更新只修改 docs / README，不修改 `app/models.py`，不生成新的 migration，也不执行 `flask db migrate` 或 `flask db upgrade`。
