# 数据库设计

最后更新：2026-06-04

本文以当前 `app/models.py` 为准，说明 Gatherly Web 当前真实数据库模型。当前正式数据库是 Neon PostgreSQL；SQLite 只是在未设置 `DATABASE_URL` 时的本地开发 fallback，不是生产数据库。

ER 图见：[er-diagram.md](er-diagram.md)。

## 当前方案

| 项目 | 当前方案 |
|---|---|
| 正式数据库 | Neon PostgreSQL |
| 本地 fallback | SQLite，仅用于本地快速开发 |
| ORM | Flask-SQLAlchemy |
| 迁移工具 | Flask-Migrate / Alembic |
| 模型定义 | `app/models.py` |
| 迁移目录 | `migrations/` |
| 生产入口 | Render Web Service, `gunicorn wsgi:app` |

生产环境不再依赖 `db.create_all()` 作为正式建表或改表方式。`init_db.py` 中的 `db.create_all()` 只允许在 SQLite 本地 fallback 下运行，不作为生产 schema 变更流程。

生产 schema 来源是 `migrations/`。`ensure_*_schema()` helper 仅用于 SQLite 本地 fallback 或历史兼容；在 Render / Neon PostgreSQL 上不应自动建表、补列或创建索引。任何数据库结构变更都必须通过 `flask db migrate` 生成 migration，并通过 `flask db upgrade` 应用。

## 数据存储边界

数据库保存：

- 用户账号、管理员账号、资料、状态、角色和信任分。
- 活动、报名记录、收藏、评分、互评和信任分日志。
- 同好圈、圈子成员、帖子、评论、互动记录。
- 私信、会话状态、通知、管理员日志。
- 邮箱验证码记录。
- 商家认证记录。
- 图片 R2 public URL。

数据库不保存：

- 图片文件本体。
- `.env`。
- Neon 数据库密码。
- R2 Secret。
- Render Environment 真实值。
- 数据库备份文件。
- 图片备份文件。

GitHub 只保存代码、模板、CSS、JS、README、docs、scripts 和 migrations。真实用户数据、真实图片、数据库密码、R2 Secret、`.env`、数据库备份和图片备份不能提交到 GitHub。

## 图片字段策略

当前代码通过 `app/services/storage.py` 上传图片。生产环境应配置 Cloudflare R2，bucket 用途按 `gatherly-uploads` 这一类上传文件 bucket 描述。上传成功后，数据库字段保存 R2 public URL，不保存文件本体。

当前图片字段按 URL 语义命名。生产环境上传成功后保存 R2 public URL；未配置 R2 的非生产本地 fallback 可能保存 `/static/uploads/...`，仅用于本地开发或历史数据。

| 字段 | 当前含义 |
|---|---|
| `User.avatar` | 头像 URL；可为 R2 URL，也可能保留历史本地静态路径。 |
| `Activity.image` | 活动图片 URL；生产环境应为 R2 URL。 |
| `Circle.cover_image` | 圈子封面 URL；生产环境应为 R2 URL。 |
| `PostImage.image_url` | 帖子图片 URL。 |
| `CommentImage.image_url` | 评论图片 URL。 |
| `DirectMessage.image_url` | 私信图片 URL。 |
| `MerchantVerification.document_url` | 认证材料 URL。 |

迁移记录：`b2c6f7e8a9d0_rename_media_path_fields_to_url.py` 将历史 `image_path` / `document_path` 列原地重命名为 `image_url` / `document_url`，不新建列丢弃旧数据。`c4d5e6f7a8b9_repair_media_url_columns.py` 兜底修复已 stamp 到旧 head 或混合字段状态的数据库：旧列存在时先重命名或复制旧值，再确保 `document_url` / `image_url` 可查询。

执行 `flask db upgrade` 后，数据库才会拥有当前模型查询所需的 `post_image.image_url`、`comment_image.image_url`、`direct_message.image_url` 和 `merchant_verification.document_url`。Render / Neon PostgreSQL 必须对 Neon Direct URL 执行升级；本地 SQLite fallback 如果出现 `no such column`，应先执行 `flask db upgrade`，历史未 stamp 的本地库可由 SQLite 兼容 helper 在应用启动时补齐字段。

### 上传限制与压缩策略

统一配置来源：`app/utils/upload_limits.py`。Flask 全局 `MAX_CONTENT_LENGTH` 仅作为 20 MB 硬上限；具体限制仍按上传场景执行。

| 场景 | 单文件上限 | 数量上限 | 保存格式 | 压缩策略 |
|---|---:|---:|---|---|
| 头像 | 2 MB | 1 | WebP | 最大 512 x 512，去 EXIF |
| 活动图片 | 5 MB | 1 | WebP | 最大 1600 x 900，去 EXIF |
| 帖子图片 | 5 MB | 9 | WebP | 长边最大 1600，去 EXIF |
| 评论图片 | 3 MB | 3 | WebP | 长边最大 1280，去 EXIF |
| 私信图片 | 3 MB | 3 | WebP | 长边最大 1280，去 EXIF |
| 圈子封面 | 5 MB | 1 | WebP | 最大 1600 x 900，去 EXIF |
| 商家认证材料 | 8 MB | 1 | WebP 或 PDF | 图片长边最大 2000；PDF 保留原格式 |

当前 `MerchantVerification.document_url` 是单 URL 字段，因此商家认证材料当前仍按单文件上传处理；如果后续要支持 3 个材料文件，应先设计多文件数据结构或单独附件表。

## 模型总览

| 模型 | 表名 | 业务含义 |
|---|---|---|
| `User` | `user` | 用户、管理员和商家账号基础资料。 |
| `Activity` | `activity` | 活动主体。 |
| `Registration` | `registration` | 活动报名记录。 |
| `ActivityFavorite` | `activity_favorite` | 活动收藏记录。 |
| `Circle` | `circle` | 同好圈。 |
| `CircleMember` | `circle_member` | 圈子成员关系。 |
| `Post` | `post` | 圈子帖子。 |
| `PostImage` | `post_image` | 帖子图片 URL 记录。 |
| `Comment` | `comment` | 活动或帖子评论。 |
| `CommentImage` | `comment_image` | 评论图片 URL 记录。 |
| `Interaction` | `interaction` | 通用互动记录。 |
| `Review` | `review` | 旧版活动单项评分。 |
| `ActivityReview` | `activity_review` | 活动多维评分。 |
| `UserReview` | `user_review` | 活动参与者互评。 |
| `TrustScoreLog` | `trust_score_log` | 用户信任分变更日志。 |
| `ProfileVisibility` | `profile_visibility` | 用户主页可见性设置。 |
| `UserFollow` | `user_follow` | 用户关注关系。 |
| `DirectMessage` | `direct_message` | 私信消息。 |
| `DirectMessageConversationState` | `direct_message_conversation_state` | 用户侧私信会话状态。 |
| `Notification` | `notification` | 站内通知。 |
| `EmailVerificationCode` | `email_verification_code` | 邮箱验证码。 |
| `MerchantVerification` | `merchant_verification` | 商家认证申请。 |
| `AdminLog` | `admin_log` | 管理员操作日志。 |

当前没有名为 `Rating` 的模型；评分由 `Review`、`ActivityReview` 和 `UserReview` 承担。

## 字段定义

表格中的“约束/索引”列只记录当前 `app/models.py` 中声明的主键、外键、唯一约束、检查约束和 `index=True`。部分 SQLite 兼容 helper 运行时创建的历史索引不作为正式 PostgreSQL schema 设计来源。

### User / `user`

业务含义：用户账号、管理员账号、商家角色、资料、登录凭据、状态和信任分。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 用户 ID |
| `username` | String(80) | 否 | 无 | Unique | 登录用户名 |
| `nickname` | String(80) | 是 | 无 |  | 昵称 |
| `email` | String(120) | 否 | 无 | Unique | 邮箱 |
| `email_verified_at` | DateTime | 是 | 无 |  | 邮箱验证时间 |
| `password` | String(255) | 否 | 无 |  | 密码哈希，模型属性名为 `password_hash` |
| `avatar` | String(255) | 是 | 无 |  | 头像 URL |
| `bio` | Text | 是 | 无 |  | 个人简介 |
| `interests` | Text | 是 | 无 |  | 兴趣文本 |
| `city` | String(80) | 是 | 无 |  | 用户填写城市 |
| `nearby_enabled` | Boolean | 否 | `False` |  | 附近的人开关 |
| `detected_city` | String(80) | 是 | 无 |  | 粗略定位城市 |
| `detected_region` | String(80) | 是 | 无 |  | 粗略定位地区 |
| `last_location_detected_at` | DateTime | 是 | 无 |  | 最近定位时间 |
| `last_ip` | String(45) | 是 | 无 |  | 最近 IP |
| `role` | String(20) | 否 | `user` |  | 角色 |
| `trust_score` | Integer | 否 | `100` |  | 信任分 |
| `status` | String(20) | 否 | `active` |  | 账号状态 |
| `banned_at` | DateTime | 是 | 无 |  | 封禁时间 |
| `deleted_at` | DateTime | 是 | 无 |  | 注销时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：一个用户可创建多个活动、报名、收藏、帖子、评论、评分、私信、通知、关注关系、商家认证和管理员日志；可拥有一份 `ProfileVisibility`。

### Activity / `activity`

业务含义：活动主体，保存活动内容、时间地点、人数、费用、标签、图片 URL、圈子和组织者。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 活动 ID |
| `title` | String(120) | 否 | 无 |  | 标题 |
| `description` | Text | 是 | 无 |  | 简介 |
| `detail` | Text | 是 | 无 |  | 详情 |
| `city` | String(80) | 是 | 无 |  | 城市 |
| `location` | String(255) | 是 | 无 |  | 地点 |
| `start_time` | DateTime | 是 | 无 |  | 开始时间 |
| `end_time` | DateTime | 是 | 无 |  | 结束时间 |
| `timezone` | String(80) | 否 | `Asia/Shanghai` |  | 时区 |
| `max_participants` | Integer | 是 | 无 |  | 人数上限 |
| `initial_participants` | Integer | 否 | `0` |  | 初始参与数 |
| `image` | String(255) | 是 | 无 |  | 活动图片 URL |
| `fee` | Float | 否 | `0` |  | 费用 |
| `tags` | Text | 是 | 无 |  | 标签文本 |
| `circle_id` | Integer | 是 | 无 | FK -> `circle.id` | 所属圈子 |
| `status` | String(20) | 否 | `open` |  | 状态 |
| `cancel_reason` | Text | 是 | 无 |  | 取消原因 |
| `cancelled_at` | DateTime | 是 | 无 |  | 取消时间 |
| `is_featured` | Boolean | 否 | `False` |  | 是否精选 |
| `is_official` | Boolean | 否 | `False` |  | 是否官方 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `organizer_id` | Integer | 否 | 无 | FK -> `user.id` | 组织者 |
| `preparation` | Text | 是 | 无 |  | 准备事项 |

关系：属于一个组织者，可选关联一个圈子；可有多个报名、收藏、评论、旧版评分、活动评分和用户互评。

### Registration / `registration`

业务含义：用户报名活动记录。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 报名 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id`; Unique(`user_id`, `activity_id`) | 报名用户 |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id`; Unique(`user_id`, `activity_id`) | 活动 |
| `status` | String(20) | 否 | `registered` |  | 报名状态 |
| `cancel_reason` | Text | 是 | 无 |  | 取消原因 |
| `cancelled_at` | DateTime | 是 | 无 |  | 取消时间 |
| `register_time` | DateTime | 否 | `datetime.utcnow` |  | 报名时间 |

关系：多条报名属于一个用户和一个活动。

约束：`uq_registration_user_activity` 保证 `user_id + activity_id` 唯一，防止同一用户重复报名同一活动。

### EmailVerificationCode / `email_verification_code`

业务含义：注册、修改邮箱、修改密码、找回密码等场景的邮箱验证码。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 验证码 ID |
| `user_id` | Integer | 是 | 无 | FK -> `user.id` | 关联用户 |
| `email` | String(120) | 否 | 无 | Index | 邮箱 |
| `code` | String(128) | 否 | 无 |  | 验证码或哈希 |
| `purpose` | String(30) | 否 | `register` |  | 用途 |
| `expires_at` | DateTime | 否 | 无 |  | 过期时间 |
| `used_at` | DateTime | 是 | 无 |  | 使用时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：可选属于一个用户。

### Notification / `notification`

业务含义：站内通知。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 通知 ID |
| `recipient_id` | Integer | 否 | 无 | FK -> `user.id`, Index | 接收用户 |
| `type` | String(50) | 否 | 无 |  | 通知类型 |
| `title` | String(120) | 否 | 无 |  | 标题 |
| `content` | Text | 是 | 无 |  | 内容 |
| `related_type` | String(50) | 是 | 无 |  | 关联对象类型 |
| `related_id` | Integer | 是 | 无 |  | 关联对象 ID |
| `read_at` | DateTime | 是 | 无 | Index | 已读时间 |
| `expires_at` | DateTime | 否 | 无 | Index | 过期时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：属于一个接收用户。`related_type` / `related_id` 是通用引用，不是数据库外键。

### DirectMessage / `direct_message`

业务含义：私信消息。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 消息 ID |
| `sender_id` | Integer | 否 | 无 | FK -> `user.id` | 发送者 |
| `recipient_id` | Integer | 否 | 无 | FK -> `user.id` | 接收者 |
| `content` | Text | 是 | 无 |  | 文本内容 |
| `message_type` | String(20) | 否 | `text` |  | 消息类型 |
| `image_url` | String(255) | 是 | 无 |  | 图片 URL |
| `read_at` | DateTime | 是 | 无 | Index | 已读时间 |
| `expires_at` | DateTime | 否 | 无 | Index | 过期时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：一条消息属于一个发送者和一个接收者。

### DirectMessageConversationState / `direct_message_conversation_state`

业务含义：某个用户视角下与另一用户的会话隐藏、删除和清空状态。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 会话状态 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id`, Index | 当前用户 |
| `other_user_id` | Integer | 否 | 无 | FK -> `user.id`, Index | 对方用户 |
| `is_hidden` | Boolean | 否 | `False` |  | 是否隐藏 |
| `hidden_at` | DateTime | 是 | 无 |  | 隐藏时间 |
| `is_deleted` | Boolean | 否 | `False` |  | 是否删除 |
| `deleted_at` | DateTime | 是 | 无 |  | 删除时间 |
| `cleared_at` | DateTime | 是 | 无 |  | 清空时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

约束：`uq_direct_message_conversation_state_pair` 保证 `user_id + other_user_id` 唯一；`ck_direct_message_conversation_state_not_self` 禁止自己与自己形成会话状态。

关系：关联当前用户和对方用户。

### UserFollow / `user_follow`

业务含义：用户关注关系。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 关注记录 ID |
| `follower_id` | Integer | 否 | 无 | FK -> `user.id`, Index | 关注者 |
| `followed_id` | Integer | 否 | 无 | FK -> `user.id`, Index | 被关注者 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

约束：`uq_user_follow_pair` 保证 `follower_id + followed_id` 唯一；`ck_user_follow_not_self` 禁止关注自己。

关系：关联关注者和被关注者。

### MerchantVerification / `merchant_verification`

业务含义：商家认证申请和审核记录。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 认证 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 申请用户 |
| `business_name` | String(120) | 否 | 无 |  | 商家名称 |
| `license_number` | String(120) | 是 | 无 |  | 证照编号 |
| `document_url` | String(255) | 是 | 无 |  | 认证材料 URL |
| `reason` | Text | 是 | 无 |  | 申请说明 |
| `contact` | String(160) | 是 | 无 |  | 联系方式 |
| `status` | String(20) | 否 | `pending` |  | 审核状态 |
| `reject_reason` | Text | 是 | 无 |  | 驳回原因 |
| `reviewer_id` | Integer | 是 | 无 | FK -> `user.id` | 审核管理员 |
| `reviewed_at` | DateTime | 是 | 无 |  | 审核时间 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

关系：属于申请用户；可关联审核管理员。

### ActivityFavorite / `activity_favorite`

业务含义：用户收藏活动。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 收藏 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 用户 |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 活动 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 收藏时间 |

约束：`uq_activity_favorite_user_activity` 保证 `user_id + activity_id` 唯一。

关系：属于一个用户和一个活动。

### Circle / `circle`

业务含义：同好圈主体。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 圈子 ID |
| `name` | String(120) | 否 | 无 |  | 名称 |
| `tag` | String(50) | 是 | 无 |  | 标签 |
| `cover_image` | String(255) | 是 | 无 |  | 封面图片 URL |
| `description` | Text | 是 | 无 |  | 简介 |
| `announcement` | Text | 是 | 无 |  | 公告 |
| `owner_id` | Integer | 是 | 无 | FK -> `user.id` | 圈主 |
| `pinned_post_id` | Integer | 是 | 无 | FK -> `post.id` | 置顶帖子 |
| `is_pinned` | Boolean | 否 | `False` |  | 是否置顶圈子 |
| `pinned_at` | DateTime | 是 | 无 |  | 置顶时间 |
| `is_system` | Boolean | 否 | `False` |  | 是否系统圈子 |
| `initial_member_count` | Integer | 否 | `0` |  | 初始成员数 |
| `member_count` | Integer | 否 | `0` |  | 成员数缓存 |
| `status` | String(20) | 否 | `active` |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

关系：可有圈主、置顶帖子、多个帖子、活动和成员。

### Post / `post`

业务含义：圈子帖子。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 帖子 ID |
| `title` | String(200) | 否 | 无 |  | 标题 |
| `content` | Text | 否 | 无 |  | 内容 |
| `type` | String(20) | 否 | `share` |  | 类型 |
| `status` | String(20) | 否 | `published` |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 作者 |
| `circle_id` | Integer | 否 | 无 | FK -> `circle.id` | 所属圈子 |

关系：属于一个用户和一个圈子；可有多个图片和评论。

### PostImage / `post_image`

业务含义：帖子图片 URL 记录。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 图片 ID |
| `post_id` | Integer | 否 | 无 | FK -> `post.id` | 所属帖子 |
| `image_url` | String(255) | 否 | 无 |  | 图片 URL |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：属于一个帖子。

### ActivityReview / `activity_review`

业务含义：活动多维评分。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 活动评分 ID |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 活动 |
| `reviewer_id` | Integer | 否 | 无 | FK -> `user.id` | 评分用户 |
| `organization_score` | Integer | 否 | 无 |  | 组织评分 |
| `venue_score` | Integer | 否 | 无 |  | 场地评分 |
| `content_score` | Integer | 否 | 无 |  | 内容评分 |
| `value_score` | Integer | 否 | 无 |  | 价值评分 |
| `experience_score` | Integer | 否 | 无 |  | 体验评分 |
| `average_score` | Float | 否 | 无 |  | 平均分 |
| `comment` | Text | 是 | 无 |  | 评价文字 |
| `status` | String(20) | 否 | `published` |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

约束：`uq_activity_review_activity_reviewer` 保证一个用户对同一活动只提交一条活动评分。

关系：属于一个活动和一个评分用户。

### UserReview / `user_review`

业务含义：活动参与者之间的互评。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 用户互评 ID |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 活动 |
| `reviewer_id` | Integer | 否 | 无 | FK -> `user.id` | 评价者 |
| `reviewee_id` | Integer | 否 | 无 | FK -> `user.id` | 被评价者 |
| `punctuality_score` | Integer | 否 | 无 | Check 1-5 | 准时评分 |
| `friendliness_score` | Integer | 否 | 无 | Check 1-5 | 友善评分 |
| `communication_score` | Integer | 否 | 无 | Check 1-5 | 沟通评分 |
| `reliability_score` | Integer | 否 | 无 | Check 1-5 | 可靠评分 |
| `respect_score` | Integer | 否 | 无 | Check 1-5 | 尊重评分 |
| `safety_score` | Integer | 否 | 无 | Check 1-5 | 安全评分 |
| `average_score` | Float | 否 | 无 |  | 平均分 |
| `comment` | Text | 是 | 无 |  | 评价文字 |
| `status` | String(20) | 否 | `published` |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

约束：`uq_user_review_activity_reviewer_reviewee` 保证同一活动中同一评价者对同一被评价者只评价一次；六个评分字段各有 1-5 检查约束。

关系：属于一个活动，关联评价者和被评价者。

### TrustScoreLog / `trust_score_log`

业务含义：用户信任分变更记录。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 日志 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 被影响用户 |
| `changed_by_id` | Integer | 是 | 无 | FK -> `user.id` | 操作者 |
| `change_type` | String(50) | 否 | 无 |  | 变更类型 |
| `delta` | Integer | 否 | 无 |  | 分数变化 |
| `score_before` | Integer | 否 | 无 |  | 变更前分数 |
| `score_after` | Integer | 否 | 无 |  | 变更后分数 |
| `reason` | Text | 是 | 无 |  | 原因 |
| `related_type` | String(50) | 是 | 无 |  | 关联对象类型 |
| `related_id` | Integer | 是 | 无 |  | 关联对象 ID |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：属于被影响用户，可关联操作者。

### CircleMember / `circle_member`

业务含义：用户与圈子的成员关系。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 成员记录 ID |
| `circle_id` | Integer | 否 | 无 | FK -> `circle.id` | 圈子 |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 用户 |
| `role` | String(20) | 否 | `member` |  | 成员角色 |
| `status` | String(20) | 否 | `active` |  | 成员状态 |
| `joined_at` | DateTime | 否 | `datetime.utcnow` |  | 加入时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

约束：`uq_circle_member_circle_user` 保证 `circle_id + user_id` 唯一。

关系：属于一个圈子和一个用户。

### Comment / `comment`

业务含义：活动或帖子评论，支持父评论形成回复。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 评论 ID |
| `author_id` | Integer | 否 | 无 | FK -> `user.id` | 作者 |
| `activity_id` | Integer | 是 | 无 | FK -> `activity.id` | 目标活动 |
| `post_id` | Integer | 是 | 无 | FK -> `post.id` | 目标帖子 |
| `parent_id` | Integer | 是 | 无 | FK -> `comment.id` | 父评论 |
| `content` | Text | 否 | 无 |  | 评论内容 |
| `status` | String(20) | 否 | `published` |  | 状态 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

约束：`ck_comment_single_target` 要求评论目标必须且只能是活动或帖子之一。

关系：属于作者；可属于活动或帖子；可有父评论和多个回复；可有多张图片。

### CommentImage / `comment_image`

业务含义：评论图片 URL 记录。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 图片 ID |
| `comment_id` | Integer | 否 | 无 | FK -> `comment.id` | 评论 |
| `image_url` | String(255) | 否 | 无 |  | 图片 URL |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：属于一条评论。

### Interaction / `interaction`

业务含义：点赞、收藏、分享等通用互动记录。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 互动 ID |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 用户 |
| `target_type` | String(30) | 否 | 无 |  | 目标类型 |
| `target_id` | Integer | 否 | 无 |  | 目标 ID |
| `action_type` | String(20) | 否 | 无 |  | 动作类型 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

约束：`uq_interaction_user_target_action` 保证 `user_id + target_type + target_id + action_type` 唯一。`target_type` / `target_id` 是通用引用，不是数据库外键。

关系：属于一个用户。

### ProfileVisibility / `profile_visibility`

业务含义：用户主页可见性设置。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
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
| `updated_at` | DateTime | 否 | `datetime.utcnow`, `onupdate=datetime.utcnow` |  | 更新时间 |

约束：`uq_profile_visibility_user` 保证每个用户只有一份配置。

关系：属于一个用户。

### AdminLog / `admin_log`

业务含义：管理员操作日志。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 日志 ID |
| `admin_id` | Integer | 否 | 无 | FK -> `user.id` | 管理员 |
| `action` | String(80) | 否 | 无 |  | 操作名 |
| `target_type` | String(50) | 否 | 无 |  | 目标类型 |
| `target_id` | Integer | 是 | 无 |  | 目标 ID |
| `detail` | Text | 是 | 无 |  | 详情 |
| `ip_address` | String(45) | 是 | 无 |  | IP 地址 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：属于执行操作的管理员用户。

### Review / `review`

业务含义：旧版活动单项评分，保留用于兼容旧流程。

| 字段 | 类型 | 可空 | 默认值 | 约束/索引 | 含义 |
|---|---|---:|---|---|---|
| `id` | Integer | 否 | 无 | PK | 评分 ID |
| `activity_id` | Integer | 否 | 无 | FK -> `activity.id` | 活动 |
| `user_id` | Integer | 否 | 无 | FK -> `user.id` | 评分用户 |
| `rating` | Integer | 否 | 无 |  | 单项评分 |
| `comment` | Text | 是 | 无 |  | 评价文字 |
| `created_at` | DateTime | 否 | `datetime.utcnow` |  | 创建时间 |

关系：属于一个活动和一个用户。

## 数据库修改流程

数据库字段变更必须单独评估，推荐单独 PR。

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
6. 执行迁移：

   ```powershell
   flask db upgrade
   ```

7. 提交 `app/models.py` 和 `migrations/`。
8. 开 GitHub PR，合并到 `main` 后 Render 自动部署新代码。

普通代码改动不需要手动改 Neon 或 R2。只有数据库 schema 变化需要迁移；图片文件本体始终进 R2，当前数据库上传字段只保存 R2 public URL。

## 当前需要另开 Issue 的问题

| 问题 | 建议 |
|---|---|
| `ensure_*_schema()` 仍保留 SQLite 兼容逻辑 | 仅作为本地 fallback 或历史兼容；生产 schema 来源是 `migrations/`，结构变更必须通过 `flask db migrate` / `flask db upgrade`。 |
