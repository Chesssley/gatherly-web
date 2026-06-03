# 部署指南

最后更新：2026-06-04

本文说明 Gatherly Web 当前正式部署方案。当前正式架构是：

- Deployment / Web Runtime：Render
- Database：Neon PostgreSQL
- Object Storage：Cloudflare R2
- Version Control：GitHub
- Database Migration：Flask-Migrate / Alembic migrations
- Production 入口：Render Web Service，启动命令 `gunicorn wsgi:app`

旧的 PythonAnywhere + SQLite + 本地上传图片方案只属于历史阶段，不再作为当前正式部署方案。历史材料如需查看，只能在 `docs/archive/` 下作为旧方案参考。

## 当前部署架构

| 层级 | 服务 | 职责 |
|---|---|---|
| Web Runtime | Render Web Service | 从 GitHub 拉取代码，安装依赖，运行 `gunicorn wsgi:app`。 |
| Database | Neon PostgreSQL | 保存用户、活动、报名、圈子、帖子、评论、评分、私信、通知、管理员日志和图片 URL。 |
| Object Storage | Cloudflare R2 | 保存用户上传图片和认证材料文件本体。 |
| Version Control | GitHub | 保存代码、模板、CSS、JS、README、docs、scripts 和 migrations。 |
| Migration | Flask-Migrate / Alembic | 管理 PostgreSQL schema 版本。 |

Render 不作为持久化数据存储，不长期保存用户上传图片、SQLite 数据库或真实用户数据。上传文件进入 R2，业务数据进入 Neon，Render 只负责运行 Web 服务。

## 线上同步流程

标准流程：

1. 本地从最新 `main` 新建分支。
2. 修改代码或文档。
3. commit。
4. push 到 GitHub。
5. 打开 GitHub Pull Request。
6. Review 后 merge 到 `main`。
7. Render 自动从 `main` 部署。

不要直接 push 到 `main`。不要在 Render 上手工改代码作为正式同步方式。

## 普通代码改动

普通代码、模板、CSS、JS、README 或 docs 改动：

- 只需要走 GitHub PR。
- 不需要手动改 Neon。
- 不需要手动改 R2。
- 合并到 `main` 后等待 Render 自动部署。

## 数据库字段改动

涉及 `app/models.py` 字段、表、外键、唯一约束、索引或默认值的改动必须生成 migration。

PowerShell 示例：

```powershell
$env:FLASK_APP='wsgi:app'
$env:DATABASE_URL='<Neon Direct URL, not the pooler URL>'
flask db migrate -m "describe schema change"
flask db upgrade
```

规则：

- 使用 Neon Direct URL 执行 `flask db migrate` 和 `flask db upgrade`。
- Render 运行时连接使用 Neon pooled URL。
- 不要依赖 `db.create_all()` 做生产 schema 变更。
- 必须提交 `migrations/versions/*.py`。
- PR 中说明迁移影响、是否会改已有数据、是否需要维护窗口。

## 图片上传逻辑改动

图片上传相关代码在 `app/services/storage.py` 和 `app/utils/upload_utils.py`。

当前策略：

- 代码进入 GitHub。
- R2 密钥进入 Render Environment。
- 上传图片文件本体进入 Cloudflare R2。
- Neon PostgreSQL 只保存 URL / object key。
- 数据库字段不保存图片文件本体。

如果改上传目录、bucket key 规则或 public URL 规则，需要同时检查：

- `R2_BUCKET_NAME`
- `R2_PUBLIC_BASE_URL`
- `app/services/storage.py`
- `scripts/migrate_uploads_to_r2.py`
- `docs/database-design.md`

## Render 配置

在 Render 创建 Web Service，连接 GitHub 仓库。

| 配置项 | 建议值 |
|---|---|
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn wsgi:app` |
| Branch | `main` |
| Root Directory | 仓库根目录 |

当前仓库存在 `wsgi.py`，作为 Render / gunicorn 入口。当前仓库没有 `render.yaml`，因此 Render 配置以 Dashboard 中的 Web Service 设置为准。

## Render Environment

不要在文档里写真实值。Render Environment 至少应保存：

```text
DATABASE_URL=<Neon pooled URL for runtime>
SECRET_KEY=<strong secret>
APP_ENV=production
SESSION_COOKIE_SECURE=true
R2_ACCOUNT_ID=<Cloudflare account id>
R2_ACCESS_KEY_ID=<R2 access key id>
R2_SECRET_ACCESS_KEY=<R2 secret access key>
R2_BUCKET_NAME=gatherly-uploads
R2_PUBLIC_BASE_URL=<public bucket or custom domain base URL>
ADMIN_USERNAME=<admin username>
ADMIN_EMAIL=<admin email>
ADMIN_PASSWORD=<admin password>
```

如果启用 Brevo 邮件：

```text
EMAIL_PROVIDER=brevo
BREVO_API_KEY=<brevo api key>
BREVO_SENDER_EMAIL=<verified sender email>
BREVO_SENDER_NAME=Gatherly
EMAIL_API_TIMEOUT=15
```

如果启用 SMTP，则使用 `MAIL_SERVER`、`MAIL_PORT`、`MAIL_USERNAME`、`MAIL_PASSWORD`、`MAIL_USE_TLS`、`MAIL_DEFAULT_SENDER`。真实密码和 API key 只放 Render Environment，不写入 GitHub。

## Neon PostgreSQL

Neon 用于正式生产数据。

连接 URL 用途：

| URL 类型 | 用途 |
|---|---|
| Pooled URL | Render Web Service 运行时连接。 |
| Direct URL | 本地迁移、维护、`flask db upgrade`。 |

Neon 中保存：

- 用户账号、管理员账号、角色、状态和资料。
- 活动、报名、收藏、评分、互评和信任分日志。
- 圈子、帖子、评论、私信、通知和管理员日志。
- 邮箱验证码和商家认证记录。
- 图片 URL / object key。

Neon 中不保存图片文件本体，不保存 R2 Secret，不保存 `.env`。

## Cloudflare R2

R2 用于上传媒体文件。当前 bucket 按 `gatherly-uploads` 这一类用途描述。

R2 保存：

- 用户头像。
- 活动图片。
- 圈子封面。
- 帖子图片。
- 评论图片。
- 私信图片。
- 商家认证材料。

Neon 保存这些文件的 URL / object key。GitHub 和 Render 不作为真实用户上传图片的长期存储。

## 本地开发 fallback

当前代码在未设置 `DATABASE_URL` 时会 fallback 到 `sqlite:///gatherly.db`。当前代码在未配置 R2 且不是生产环境时，上传会 fallback 到 `app/static/uploads/`。

这些 fallback 仅用于本地快速开发、历史数据迁移或演示，不代表生产环境：

- SQLite 不是正式数据库。
- `app/static/uploads/` 不是 Render 生产持久化目录。
- `instance/` 不是正式生产数据目录。

## 旧数据迁移

如果历史阶段存在本地 SQLite 或本地上传文件，需要先评估数据来源和敏感信息。

可用脚本：

| 脚本 | 用途 |
|---|---|
| `scripts/export_data.py` | 从当前数据库导出 JSON。 |
| `scripts/import_data.py` | 将导出的 JSON 导入 PostgreSQL / Neon。 |
| `scripts/migrate_uploads_to_r2.py` | 将历史本地上传文件迁移到 R2，并把数据库中的旧本地路径更新为 R2 URL。 |

迁移时不要把真实导出文件、数据库备份或图片备份提交到 GitHub。根目录历史备份文件应尽快移出仓库工作区或纳入安全清理计划。

## 部署后检查

| 检查项 | 预期 |
|---|---|
| Render build | `pip install -r requirements.txt` 成功。 |
| Render start | `gunicorn wsgi:app` 成功启动。 |
| 首页 | `/` 可访问。 |
| 数据库 | Neon 可看到业务表和数据。 |
| 上传 | 新上传文件进入 R2。 |
| 图片 URL | 页面加载的是 R2 public URL 或可解析的对象 URL。 |
| 登录注册 | Session 和 Cookie 正常。 |
| 管理后台 | 权限控制正常。 |
| 静态资源 | CSS、JS、favicon 和代码内置静态图片正常加载。 |

## 常见问题

| 问题 | 可能原因 | 处理 |
|---|---|---|
| Render 启动失败 | Start Command 错误 | 使用 `gunicorn wsgi:app`。 |
| 数据库连接失败 | `DATABASE_URL` 错误或 Neon 权限问题 | 重新复制 Neon pooled URL 到 Render Environment。 |
| 迁移失败 | 使用了 pooler URL 或 migration 与模型不一致 | 改用 Neon Direct URL，检查 migration。 |
| 上传失败 | R2 环境变量不完整 | 补齐 `R2_ACCOUNT_ID`、`R2_BUCKET_NAME`、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_PUBLIC_BASE_URL`。 |
| 上传成功但图片无法访问 | `R2_PUBLIC_BASE_URL` 或 bucket public access 配置错误 | 检查 R2 public bucket/custom domain。 |
| Render 文件丢失 | 把 Render 当成持久化存储 | 上传文件必须进 R2，业务数据必须进 Neon。 |

## 不再使用的正式部署方式

PythonAnywhere、SQLite 生产数据库、本地图片目录生产存储、在服务器 Bash 中 `git pull` 后 reload，都不再是当前正式部署流程。若文档中出现，只能明确标注为“旧方案 / 历史阶段”，并放在 `docs/archive/`。
