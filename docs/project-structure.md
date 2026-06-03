# 项目结构

最后更新时间：2026-06-04

本文根据当前仓库真实文件结构整理。不要以旧文档中的目录为准。

## 当前目录树

```text
gatherly-web/
├── .gitignore
├── README.md
├── gatherly_export.json
├── gatherly_uploads_backup.zip
├── init_db.py
├── requirements.txt
├── run.py
├── seed_data.py
├── wsgi.py
├── app/
│   ├── __init__.py
│   ├── forms.py
│   ├── models.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── activity.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── circle.py
│   │   ├── messages.py
│   │   ├── notifications.py
│   │   └── profile.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── storage.py
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   ├── avatar-crop.js
│   │   │   ├── circle.js
│   │   │   └── main.js
│   │   └── images/
│   │       ├── activities/
│   │       ├── circle_covers/
│   │       ├── circles/
│   │       ├── favicon.ico
│   │       └── placeholder-activity.jpg
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── activity_detail.html
│   │   ├── activity_create.html
│   │   ├── circle.html
│   │   ├── circle_detail.html
│   │   ├── create_circle.html
│   │   ├── create_post.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── profile.html
│   │   ├── messages.html
│   │   ├── notifications.html
│   │   └── admin_*.html
│   └── utils/
│       ├── email_verification.py
│       ├── location_utils.py
│       └── upload_utils.py
├── docs/
│   ├── README.md
│   ├── project-overview.md
│   ├── project-structure.md
│   ├── requirements.md
│   ├── product-backlog.md
│   ├── database-design.md
│   ├── er-diagram.md
│   ├── er-diagram.mmd
│   ├── github-workflow.md
│   ├── issue-management.md
│   ├── development-guide.md
│   ├── style-guide.md
│   ├── test-report.md
│   ├── meeting-notes.md
│   ├── deployment-guide.md
│   ├── screenshots/
│   └── archive/
├── migrations/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
└── scripts/
    ├── add_nickname_column.py
    ├── backfill_circle_covers.py
    ├── export_data.py
    ├── import_data.py
    └── migrate_uploads_to_r2.py
```

## 关键目录说明

| 路径 | 说明 |
|---|---|
| `app/` | Flask 应用主目录，包含模型、路由、模板、静态资源、服务和工具函数 |
| `app/routes/` | Flask Blueprint 路由模块，按业务域拆分 |
| `app/templates/` | Jinja2 HTML 模板目录 |
| `app/static/css/` | CSS 样式目录，当前主要文件为 `style.css` |
| `app/static/js/` | 原生 JavaScript 文件目录 |
| `app/static/images/` | 本地图片、活动图片、圈子图片、favicon 和占位图 |
| `app/services/` | 服务层辅助代码，当前包含 Cloudflare R2 对象存储 URL 和上传处理 |
| `app/utils/` | 上传、定位、邮箱验证码等工具函数 |
| `docs/` | 项目文档、ER 图、测试报告、会议记录和归档 |
| `docs/screenshots/` | 课程交付截图目录，已有截图不要删除 |
| `docs/archive/` | 历史文档归档目录 |
| `migrations/` | Flask-Migrate / Alembic 数据库迁移目录 |
| `scripts/` | 数据导入导出、Neon 数据迁移、R2 上传迁移、圈子封面补齐等脚本 |
| `instance/` | Flask instance 目录，本地 SQLite 数据库通常位于这里；一般不提交数据库文件 |

## 关键文件说明

| 文件 | 作用 | 风险 |
|---|---|---|
| `app/__init__.py` | 创建 Flask app、配置数据库、CSRF、迁移、模板过滤器，并注册所有蓝图 | 高风险 |
| `app/models.py` | 定义所有 SQLAlchemy 数据模型、关系、约束和部分 schema 兼容函数 | 高风险 |
| `app/forms.py` | WTForms 表单定义 | 中风险 |
| `app/routes/activity.py` | 首页、搜索、活动详情、发布、报名、收藏、评论、评分和我的活动 | 中高风险 |
| `app/routes/auth.py` | 注册、登录、退出、邮箱验证码、账号设置和密码相关流程 | 中高风险 |
| `app/routes/circle.py` | 同好圈、成员、帖子、评论、图片和互动 | 中高风险 |
| `app/routes/profile.py` | 个人主页、用户搜索、附近的人、关注、个人内容管理 | 中高风险 |
| `app/routes/messages.py` | 私信会话、轮询、发送、隐藏和删除会话 | 中风险 |
| `app/routes/notifications.py` | 通知列表、未读数量、标记已读 | 中风险 |
| `app/routes/admin.py` | 管理员后台、用户/活动/圈子/帖子/评论/认证/日志管理 | 中高风险 |
| `app/templates/base.html` | 全站基础模板、导航栏、flash 消息和公共布局 | 中风险 |
| `app/static/css/style.css` | 全站主要样式文件，体量较大，影响所有页面视觉 | 中风险 |
| `app/static/js/main.js` | 全站主要交互脚本，影响搜索、消息、提示等交互 | 中风险 |
| `requirements.txt` | Python 依赖列表 | 高风险 |
| `run.py` | 本地启动入口，调用 `create_app()` 并启动 Flask debug server | 高风险 |
| `wsgi.py` | WSGI 部署入口 | 中风险 |
| `scripts/export_data.py` | 从当前数据库导出 `gatherly_export.json`，用于迁移到 Neon | 中风险 |
| `scripts/import_data.py` | 将 `gatherly_export.json` 导入 PostgreSQL / Neon，并修复 sequence | 中高风险 |
| `scripts/migrate_uploads_to_r2.py` | 将本地 `app/static/uploads/` 文件迁移到 Cloudflare R2 并更新数据库 URL | 中高风险 |
| `init_db.py` | 初始化数据库和部分基础数据 | 中高风险 |
| `.gitignore` | 控制哪些文件不进入 Git | 高风险 |

## 高风险文件说明

以下文件不要随便改：

- `app/models.py`
- `app/__init__.py`
- `run.py`
- `requirements.txt`
- `.gitignore`

原因：

- `app/models.py` 改动会影响数据库字段、外键、关系和迁移。
- `app/__init__.py` 改动会影响应用是否能启动、蓝图是否注册、数据库和 CSRF 是否正常。
- `run.py` 是本地运行入口，改错会导致新手无法启动项目。
- `requirements.txt` 改动会影响所有成员安装依赖，不应随意新增技术栈。
- `.gitignore` 改错可能导致数据库、缓存、上传文件或环境文件被误提交。

## 新手修改建议

1. 只改自己 Issue 对应的文件。
2. 修改前先确认当前分支，不要直接在 `main` 开发。
3. 改模板前先看 `base.html` 是否已有公共结构。
4. 改 CSS 前先搜索现有类名，优先复用当前样式。
5. 改模型前必须先和组员确认，并同步更新 `database-design.md` 和 `er-diagram.md`。
6. 不要引入 React、Vue、Bootstrap、新数据库或新依赖。
