# 项目结构

最后更新：2026-06-04

本文根据当前仓库真实结构整理。当前正式部署架构为 Render + Neon PostgreSQL + Cloudflare R2 + GitHub。

## 当前根目录

```text
gatherly-web/
|-- .gitignore
|-- README.md
|-- gatherly_export.json
|-- gatherly_uploads_backup.zip
|-- init_db.py
|-- requirements.txt
|-- run.py
|-- seed_data.py
|-- wsgi.py
|-- app/
|-- docs/
|-- instance/
|-- migrations/
`-- scripts/
```

说明：

- 当前仓库没有 `render.yaml`。Render 配置以 Render Dashboard 中的 Web Service 设置为准。
- 根目录存在 `gatherly_export.json` 和 `gatherly_uploads_backup.zip`，它们看起来像历史迁移/备份文件。真实数据库备份和图片备份不应提交到 GitHub，建议另开清理 Issue 处理。

## app/

```text
app/
|-- __init__.py
|-- forms.py
|-- models.py
|-- routes/
|   |-- __init__.py
|   |-- activity.py
|   |-- admin.py
|   |-- auth.py
|   |-- circle.py
|   |-- messages.py
|   |-- notifications.py
|   `-- profile.py
|-- services/
|   |-- __init__.py
|   `-- storage.py
|-- static/
|   |-- css/
|   |   `-- style.css
|   |-- images/
|   |   |-- activities/
|   |   |-- circle_covers/
|   |   |-- circles/
|   |   |-- favicon.ico
|   |   `-- placeholder-activity.jpg
|   |-- js/
|   |   |-- avatar-crop.js
|   |   |-- circle.js
|   |   `-- main.js
|   `-- uploads/
|       |-- avatars/
|       |-- circle/
|       |-- comments/
|       `-- messages/
|-- templates/
`-- utils/
    |-- email_verification.py
    |-- location_utils.py
    `-- upload_utils.py
```

| 路径 | 说明 |
|---|---|
| `app/__init__.py` | Flask app factory，初始化数据库、Flask-Migrate、CSRF、模板过滤器和蓝图。`DATABASE_URL` 存在时连接对应数据库；否则本地 fallback 到 SQLite。 |
| `app/models.py` | 所有 SQLAlchemy 模型、关系、约束和部分 SQLite 兼容 helper。高风险文件。 |
| `app/routes/` | 按业务域拆分的 Flask Blueprint 路由。 |
| `app/services/storage.py` | Cloudflare R2 上传、删除、URL 处理和本地 fallback 逻辑。生产环境必须配置 R2。 |
| `app/utils/upload_utils.py` | 图片类型校验、大小校验、上传保存和删除封装。 |
| `app/static/images/` | 代码内置静态图片、默认图、favicon 和课程演示图片。不是用户真实上传图片的生产存储。 |
| `app/static/uploads/` | 当前仓库存在的历史上传目录 / 本地开发 fallback。Render 生产环境不能把它当作持久化存储；生产上传应进入 Cloudflare R2。 |
| `app/templates/` | Jinja2 HTML 模板。 |

## docs/

```text
docs/
|-- README.md
|-- project-overview.md
|-- project-structure.md
|-- requirements.md
|-- product-backlog.md
|-- database-design.md
|-- er-diagram.md
|-- er-diagram.mmd
|-- deployment-guide.md
|-- development-guide.md
|-- maintenance-guide.md
|-- github-workflow.md
|-- issue-management.md
|-- test-report.md
|-- meeting-notes.md
|-- style-guide.md
|-- screenshots/
`-- archive/
```

| 路径 | 说明 |
|---|---|
| `docs/database-design.md` | 当前真实数据库模型说明，正式数据库为 Neon PostgreSQL。 |
| `docs/er-diagram.md` | 当前模型 Mermaid ER 图。 |
| `docs/er-diagram.mmd` | Mermaid 源文件。 |
| `docs/deployment-guide.md` | Render + Neon + R2 正式部署指南。 |
| `docs/development-guide.md` | 本地开发、迁移、PR 和安全规则。 |
| `docs/maintenance-guide.md` | 日常维护、数据库维护、R2、Render、GitHub 和泄露处理。 |
| `docs/archive/` | 历史阶段文档。旧 PythonAnywhere / SQLite / 本地上传说明只能作为历史材料保留。 |
| `docs/screenshots/er-diagram.png` | 历史 ER 图截图；当前事实来源以 `er-diagram.md` 和 `er-diagram.mmd` 为准。 |

## migrations/

```text
migrations/
|-- README
|-- alembic.ini
|-- env.py
|-- script.py.mako
`-- versions/
    `-- 52ce70c39825_initial_schema.py
```

`migrations/` 是 Flask-Migrate / Alembic 数据库迁移版本目录。它是数据库 schema 的正式版本记录，必须随 `app/models.py` 的字段变更一起提交。

生产 schema 变更流程：

```powershell
$env:FLASK_APP='wsgi:app'
$env:DATABASE_URL='<Neon Direct URL, not the pooler URL>'
flask db migrate -m "describe schema change"
flask db upgrade
```

不要依赖 `db.create_all()` 作为生产 schema 更新方式。

## scripts/

```text
scripts/
|-- add_nickname_column.py
|-- backfill_circle_covers.py
|-- export_data.py
|-- import_data.py
`-- migrate_uploads_to_r2.py
```

| 脚本 | 说明 |
|---|---|
| `scripts/export_data.py` | 导出当前数据库数据，用于迁移准备。 |
| `scripts/import_data.py` | 导入导出的 JSON 到 PostgreSQL / Neon，并修复 sequence。 |
| `scripts/migrate_uploads_to_r2.py` | 将历史本地上传文件迁移到 Cloudflare R2，并更新数据库中的 URL。 |
| `scripts/backfill_circle_covers.py` | 补齐圈子封面。 |
| `scripts/add_nickname_column.py` | 历史字段辅助脚本；当前正式 schema 应以 migrations 为准。 |

脚本可能处理真实数据。导出的 JSON、数据库备份和图片备份不要提交到 GitHub。

## instance/

`instance/` 是 Flask instance 目录。当前代码在未设置 `DATABASE_URL` 时，SQLite fallback 通常会在该目录下创建 `gatherly.db`。

这只适用于本地开发：

- `instance/` 不是正式生产数据目录。
- Render 不应长期保存 SQLite 数据库。
- 生产用户数据必须保存到 Neon PostgreSQL。

## 入口文件

| 文件 | 说明 |
|---|---|
| `wsgi.py` | Render / gunicorn 生产入口：`app = create_app()`。 |
| `run.py` | 本地开发入口，debug server。 |
| `init_db.py` | 本地初始化和演示数据初始化脚本；生产 schema 变更以 migrations 为准。 |
| `seed_data.py` | 示例数据脚本。 |
| `requirements.txt` | Python 依赖，包含 Flask、Flask-SQLAlchemy、Flask-Migrate、gunicorn、psycopg2-binary、boto3 等。 |

## 高风险文件

| 文件 | 风险 |
|---|---|
| `app/models.py` | 改动会影响数据库 schema，需要 migration。 |
| `migrations/` | 影响 Neon PostgreSQL schema，必须审查。 |
| `app/__init__.py` | 影响数据库连接、迁移初始化、蓝图注册和安全配置。 |
| `app/services/storage.py` | 影响 R2 上传、删除和本地 fallback。 |
| `requirements.txt` | 影响 Render build 和所有开发环境。 |
| `.gitignore` | 改错可能导致 `.env`、数据库或上传备份被提交。 |

## 存储边界

| 内容 | 应存放位置 |
|---|---|
| 源码、模板、CSS、JS、README、docs、migrations | GitHub |
| 用户账号、活动、报名、评分、私信、通知、日志、图片 URL | Neon PostgreSQL |
| 用户上传图片和认证材料文件本体 | Cloudflare R2 |
| 环境变量和密钥 | Render Environment / 本地 `.env` |
| Render runtime | 只运行应用，不作为持久化数据存储 |
