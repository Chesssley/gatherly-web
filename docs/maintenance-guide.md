# 维护指南

最后更新：2026-06-04

本文说明 Gatherly Web 当前 Render + Neon PostgreSQL + Cloudflare R2 + GitHub 架构下的维护流程。

## 日常代码维护

标准流程：

1. 从最新 `main` 新建分支。
2. 在本地完成修改。
3. commit。
4. push 到 GitHub。
5. 打开 Pull Request。
6. Review 后 merge 到 `main`。
7. Render 自动部署。

不要直接 push 到 `main`。不要在 Render 上手工改代码作为正式发布方式。

## 数据库维护

正式数据库是 Neon PostgreSQL。

Neon Console 常用区域：

| 区域 | 用途 |
|---|---|
| Tables | 查看表结构、字段和少量数据。 |
| SQL Editor | 执行受控 SQL 查询或维护语句。 |
| Monitoring / Usage | 查看连接、存储、计算和用量情况。 |
| Connection Details | 获取 pooled URL 和 direct URL。 |

连接 URL 用途：

| URL 类型 | 用途 |
|---|---|
| Pooled URL | Render Web Service 运行时连接。 |
| Direct URL | 本地迁移、维护和 `flask db upgrade`。 |

维护规则：

- 不在 GitHub 文档中写真实 Neon URL。
- 真实数据库备份不得提交 GitHub。
- 不在 Render 文件系统保存生产数据库。
- 生产数据只保存在 Neon。

## 数据库模型变更

数据库 schema 由 SQLAlchemy models + Flask-Migrate / Alembic migrations 管理。

流程：

```powershell
$env:FLASK_APP='wsgi:app'
$env:DATABASE_URL='<Neon Direct URL, not the pooler URL>'
flask db migrate -m "describe schema change"
flask db upgrade
```

要求：

- 修改 `app/models.py` 后必须生成 migration。
- 审查 `migrations/versions/*.py`，确认不会误删数据。
- 提交 `app/models.py` 和 `migrations/`。
- PR 中说明 schema 影响。
- 不依赖 `db.create_all()` 做生产 schema 变更。

## 图片存储维护

正式对象存储是 Cloudflare R2。bucket 当前按 `gatherly-uploads` 这一类用途描述。

R2 Console 常用区域：

| 区域 | 用途 |
|---|---|
| Buckets / Objects | 查看对象、路径、大小和上传结果。 |
| Public URL / Custom Domain | 管理图片公开访问 base URL。 |
| R2 API Token | 管理 S3-compatible API 凭据。 |
| Metrics / Usage | 查看请求和存储用量。 |

规则：

- 图片文件本体在 R2。
- 图片 URL / object key 在 Neon。
- Render 不长期保存用户上传图片。
- GitHub 不保存真实用户上传图片。
- 真实图片备份不得提交 GitHub。
- R2 Secret 只放 Render Environment 或本地 `.env`。

## Render 维护

Render Web Service 负责运行 Flask 应用。

常用区域：

| 区域 | 用途 |
|---|---|
| Logs | 查看运行日志和错误。 |
| Events / Deploys | 查看部署记录和失败原因。 |
| Metrics | 查看资源和响应情况。 |
| Environment | 管理 `DATABASE_URL`、`SECRET_KEY`、`R2_*`、`ADMIN_*` 等环境变量。 |
| Settings | 管理 build command、start command、branch 和服务设置。 |

当前建议：

- Build Command：`pip install -r requirements.txt`
- Start Command：`gunicorn wsgi:app`
- Branch：`main`
- Runtime：Python

Render Environment 中的 `DATABASE_URL` 应使用 Neon pooled URL。迁移维护时在本地使用 Neon Direct URL。

## GitHub 维护

GitHub 保存：

- 源码。
- 模板。
- CSS / JS。
- README。
- docs。
- migrations。
- scripts。

GitHub 常用区域：

| 区域 | 用途 |
|---|---|
| Pull Requests | 代码审查和合并。 |
| Branches | 分支管理。 |
| Issues | 任务和缺陷跟踪。 |
| README | 英文项目入口说明。 |
| docs | 中文项目文档。 |

GitHub 不保存：

- 真实用户数据。
- 真实图片。
- 数据库密码。
- R2 Secret。
- `.env`。
- 数据库备份。
- 图片备份。

密钥和密码只放 Render Environment 或本地 `.env`。不要提交真实用户数据、真实图片、`.env`、数据库备份、图片备份或密钥。

## 环境变量维护

Render Environment 应包含：

```text
DATABASE_URL=<Neon pooled URL>
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

如果使用 Brevo：

```text
EMAIL_PROVIDER=brevo
BREVO_API_KEY=<brevo api key>
BREVO_SENDER_EMAIL=<verified sender email>
BREVO_SENDER_NAME=Gatherly
EMAIL_API_TIMEOUT=15
```

## 安全规则

严禁提交：

- `.env`
- `DATABASE_URL`
- 数据库密码
- `SECRET_KEY`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- R2 Secret
- `ADMIN_PASSWORD`
- `BREVO_API_KEY`
- Neon 数据库备份
- 图片备份
- 真实用户数据
- 真实用户上传图片

如果需要分享配置，只写变量名和占位符。

## 泄露处理

发现密钥、数据库 URL、管理员密码、数据库备份或图片备份泄露时，按以下顺序处理：

1. 立即停止继续传播泄露内容。
2. 轮换 Neon 密码。
3. 更新 Render `DATABASE_URL`。
4. 轮换 R2 Token。
5. 更新 Render 中的 `R2_ACCESS_KEY_ID` 和 `R2_SECRET_ACCESS_KEY`。
6. 更新 `SECRET_KEY`。
7. 修改管理员密码。
8. 检查 Neon 是否有异常连接、异常 SQL 或异常数据变化。
9. 检查 R2 是否有异常对象、异常访问或异常删除。
10. 检查 Render Logs / Events / Deploys。
11. 检查 GitHub commits、PR、Issues、Actions 和访问权限。
12. 如泄露文件进入 Git 历史，另开安全清理任务，不只删除最新文件。

## 例行检查清单

| 周期 | 检查项 |
|---|---|
| 每次 PR | 是否误提交 `.env`、密钥、备份、真实图片；是否需要 migration。 |
| 每次部署后 | Render build/start、首页、登录、上传、数据库连接。 |
| 每周 | Neon usage、R2 usage、Render logs、GitHub open PRs。 |
| 每次 schema 变更 | migration 是否提交、是否在 Neon Direct URL 上执行 upgrade。 |
