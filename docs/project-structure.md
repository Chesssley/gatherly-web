# 项目结构说明

本文档说明当前仓库真实目录结构，不沿用旧文档中的过期结构。

## 顶层结构

```text
gatherly-web/
├── app/
├── docs/
├── scripts/
├── init_db.py
├── seed_data.py
├── requirements.txt
├── run.py
├── .gitignore
└── README.md
```

## `app/`

Flask 应用主目录。

```text
app/
├── __init__.py
├── forms.py
├── models.py
├── routes/
├── static/
├── templates/
└── utils/
```

### `app/__init__.py`

负责创建 Flask 应用：

- 设置 `SECRET_KEY`。
- 设置 SQLite 数据库地址 `sqlite:///gatherly.db`。
- 设置上传大小、Session Cookie 安全配置。
- 初始化 SQLAlchemy 和 CSRF。
- 调用 `ensure_task_foundation_schema()` 做 SQLite schema 兼容处理。
- 注册活动、认证、同好圈、个人主页、私信、通知和后台管理蓝图。

### `app/models.py`

定义所有 SQLAlchemy 模型和部分 schema 兼容函数。数据库设计说明见 [database-design.md](database-design.md)。

### `app/forms.py`

定义注册表单等 WTForms 表单。

## `app/routes/`

按功能拆分 Flask Blueprint：

```text
app/routes/
├── activity.py
├── admin.py
├── auth.py
├── circle.py
├── messages.py
├── notifications.py
├── profile.py
└── __init__.py
```

| 文件 | 主要职责 |
| --- | --- |
| `activity.py` | 首页、搜索、活动详情、活动发布、报名、取消报名、收藏、活动评论、参与者互评 |
| `auth.py` | 注册、登录、登出、邮箱验证码、找回密码、账号设置、商家认证申请 |
| `circle.py` | 同好圈列表、创建、详情、加入、私密访问、帖子、评论、互动、圈子管理 |
| `profile.py` | 用户主页、编辑资料、关注关系、附近的人、个人内容分区 |
| `messages.py` | 私信列表、会话、发送消息、轮询、隐藏/删除会话 |
| `notifications.py` | 通知列表、标记已读、全部已读 |
| `admin.py` | 管理员仪表盘、用户/活动/圈子/帖子/评论/商家认证管理 |

## `app/templates/`

Jinja2 模板目录。主要页面包括：

- 首页：`index.html`
- 活动：`activity_detail.html`、`activity_create.html`
- 认证：`register.html`、`login.html`、`forgot_password.html`、`account_settings.html`
- 同好圈：`circle.html`、`circle_detail.html`、`create_circle.html`、`create_post.html`
- 个人主页：`profile.html`、`edit_profile.html`、`profile_section.html`、`users.html`、`follows.html`
- 私信和通知：`messages.html`、`notifications.html`
- 管理员：`admin_dashboard.html`、`admin_users.html`、`admin_activities.html`、`admin_circles.html`、`admin_posts.html`、`admin_comments.html`、`admin_logs.html`、`admin_account.html`、`admin_merchant_verifications.html`

以下划线开头的模板是局部组件，例如 `_profile_sidebar.html`、`_user_card.html`。

## `app/static/`

静态资源目录：

```text
app/static/
├── css/
├── images/
├── js/
└── uploads/
```

- `css/style.css`：全站主要样式。
- `js/main.js`：首页、搜索、活动页等通用交互。
- `js/circle.js`：同好圈相关交互。
- `js/avatar-crop.js`：头像裁剪相关交互。
- `images/`：活动图、圈子封面、favicon 和占位图。
- `uploads/avatars/.gitkeep`：保留上传目录结构；真实上传文件不提交。

## `app/utils/`

工具模块：

- `email_verification.py`：验证码生成、哈希存储、发送和校验。
- `location_utils.py`：粗略位置识别和城市匹配。
- `upload_utils.py`：图片类型、大小、内容签名校验和保存/删除。

## `docs/`

当前有效文档位于 `docs/` 顶层：

- [project-overview.md](project-overview.md)
- [feature-guide.md](feature-guide.md)
- [project-structure.md](project-structure.md)
- [database-design.md](database-design.md)
- [er-diagram.mmd](er-diagram.mmd)
- [development-workflow.md](development-workflow.md)
- [setup-and-deployment.md](setup-and-deployment.md)
- [testing-guide.md](testing-guide.md)

历史材料统一放在 `docs/archive/`，截图和交付证据保留在 `docs/screenshots/`。

## `scripts/`

维护脚本目录：

- `add_nickname_column.py`
- `backfill_circle_covers.py`

运行脚本前应先阅读脚本内容，并确认不会影响生产或他人的数据库。

## 初始化与运行文件

| 文件 | 作用 |
| --- | --- |
| `run.py` | 本地运行入口，创建 `app` 并在直接运行时启动 debug server |
| `init_db.py` | 创建数据库表、同步基础 schema、同步系统圈子、写入 demo 活动，可选创建管理员 |
| `seed_data.py` | demo 活动数据 |
| `requirements.txt` | Python 依赖 |

## 不应提交的内容

`.gitignore` 已管理以下运行时或敏感内容：

- `.env`
- `.flaskenv`
- `.venv/`
- `venv/`
- `__pycache__/`
- `instance/`
- `instance/*.db`
- `*.sqlite`
- `*.sqlite3`
- `app/static/uploads/*` 中的真实上传文件
- 临时文件、编辑器目录和运行日志

