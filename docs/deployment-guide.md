# 部署与运行指南

最后更新时间：2026-06-04

本文说明 Gatherly Web 的本地运行方式，以及当前推荐的线上部署方案：Render + Neon PostgreSQL + Cloudflare R2。

当前代码已经具备以下部署基础：

- `wsgi.py` 可作为 WSGI 入口。
- `requirements.txt` 包含 `gunicorn`、`psycopg2-binary`、`python-dotenv`、`Flask-Migrate` 和 `boto3`。
- `app/__init__.py` 支持通过 `DATABASE_URL` 切换数据库，并会把 `postgres://` 自动转换为 `postgresql://`。
- `app/services/storage.py` 支持 Cloudflare R2。未配置 R2 时，本地开发会保存到 `app/static/uploads/`；生产环境缺少 R2 配置时会报错，避免上传文件丢失。
- `scripts/export_data.py`、`scripts/import_data.py` 和 `scripts/migrate_uploads_to_r2.py` 可用于从本地 SQLite 迁移到 Neon + R2。

## 本地运行

### 1. 准备 Python

建议使用 Python 3.10 或更新版本。

```bash
python --version
```

### 2. 创建并激活虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
python init_db.py
```

如需示例数据：

```bash
python seed_data.py
```

### 5. 启动应用

```bash
python run.py
```

浏览器打开：

```text
http://127.0.0.1:5000/
```

## 推荐线上架构

| 服务 | 用途 | 项目中的对应配置 |
|---|---|---|
| Render Web Service | 托管 Flask Web 应用 | `gunicorn wsgi:app` |
| Neon PostgreSQL | 线上数据库 | `DATABASE_URL` |
| Cloudflare R2 | 上传图片、头像、帖子图、评论图、私信图和认证材料 | `R2_*` 环境变量 |

官方参考：

- Render Flask 部署文档：https://render.com/docs/deploy-flask
- Neon 连接文档：https://neon.com/docs/get-started-with-neon/connect-neon
- Cloudflare R2 S3 API 文档：https://developers.cloudflare.com/r2/get-started/s3/

## Render + Neon + Cloudflare R2 部署方案

### 1. 创建 Neon 数据库

1. 在 Neon 创建一个 PostgreSQL project。
2. 复制数据库连接字符串。
3. 优先使用适合服务端应用的连接字符串，并确认包含数据库名、用户名、密码、host 和 SSL 参数。
4. 将连接字符串作为 Render 环境变量 `DATABASE_URL`。

示例格式：

```text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

如果 Neon 给出的连接串以 `postgres://` 开头也可以使用，当前 `app/__init__.py` 会自动转换为 `postgresql://`。

### 2. 创建 Cloudflare R2 Bucket

1. 在 Cloudflare R2 创建 bucket。
2. 创建 R2 API Token / Access Key。
3. 配置公开访问方式，例如 public bucket URL 或自定义域名。
4. 记录以下信息：
   - Account ID
   - Bucket name
   - Access Key ID
   - Secret Access Key
   - Public base URL

当前代码会使用 S3-compatible endpoint：

```text
https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
```

上传后的公开 URL 格式由 `R2_PUBLIC_BASE_URL` 决定。

### 3. 创建 Render Web Service

在 Render 中选择从 GitHub 仓库创建 Web Service。

建议配置：

| 配置项 | 建议值 |
|---|---|
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn wsgi:app` |
| Root Directory | 仓库根目录 |
| Branch | 需要部署的分支，通常为 `main` |

Render 部署前，请在 Environment 中配置下面的环境变量。

## 线上环境变量表

| 变量名 | 必填 | 示例 / 说明 |
|---|---|---|
| `SECRET_KEY` | 是 | 生产环境必须使用强随机字符串，不要使用默认值 |
| `DATABASE_URL` | 是 | Neon PostgreSQL 连接字符串 |
| `APP_ENV` | 是 | `production` |
| `SESSION_COOKIE_SECURE` | 是 | `true`，Render 默认提供 HTTPS |
| `R2_ACCOUNT_ID` | 是 | Cloudflare Account ID |
| `R2_BUCKET_NAME` | 是 | R2 bucket 名称 |
| `R2_ACCESS_KEY_ID` | 是 | R2 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | 是 | R2 Secret Access Key |
| `R2_PUBLIC_BASE_URL` | 是 | R2 公开访问 base URL，例如 `https://assets.example.com` |
| `ADMIN_USERNAME` | 可选 | 首次初始化管理员账号时使用 |
| `ADMIN_EMAIL` | 可选 | 首次初始化管理员账号时使用 |
| `ADMIN_PASSWORD` | 可选 | 首次初始化管理员账号时使用 |

注意：

- 不要把 `.env`、Neon 连接串、R2 secret 或管理员密码提交到 Git。
- `R2_PUBLIC_BASE_URL` 不要以 `/` 结尾，代码会自动去掉末尾斜杠。
- 生产环境如果没有配置 R2，上传功能会失败，这是预期保护行为。

## Neon 数据库初始化与数据迁移

当前仓库支持两种方式。

### 方式 A：全新线上库

适合没有历史数据的部署。

1. 在本地或 Render Shell 中设置 `DATABASE_URL` 指向 Neon。
2. 执行迁移或初始化。

优先使用迁移：

```bash
flask --app wsgi:app db upgrade
```

如果课程演示需要快速创建表和示例数据，也可以运行：

```bash
python init_db.py
```

说明：`init_db.py` 会执行 `db.create_all()`，同步系统圈子，并写入示例活动和可选管理员账号。生产化项目长期建议以迁移为准。

### 方式 B：从本地 SQLite 迁移到 Neon

适合已经在本地 SQLite 中准备好活动、用户、圈子、帖子、评论、评分等数据，需要迁移到 Neon。

#### 1. 从当前本地数据库导出 JSON

确认本地 `.env` 没有把 `DATABASE_URL` 指向 Neon，或临时 unset `DATABASE_URL`，确保导出的是本地 SQLite 数据。

```bash
python scripts/export_data.py
```

脚本会生成：

```text
gatherly_export.json
```

#### 2. 在 Neon 中创建表结构

将 `DATABASE_URL` 设置为 Neon 连接串后运行：

```bash
flask --app wsgi:app db upgrade
```

如果迁移命令不可用，可使用：

```bash
python init_db.py
```

但如果准备用 `scripts/import_data.py` 导入完整数据，建议目标库尽量保持空表，避免重复示例数据。

#### 3. 导入数据到 Neon

PowerShell 示例：

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
python scripts/import_data.py
```

macOS / Linux 示例：

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
python scripts/import_data.py
```

如果目标 Neon 数据库已有业务数据，脚本会停止，避免误删数据。确认要清空目标业务表并重新导入时，再设置：

PowerShell：

```powershell
$env:CONFIRM_IMPORT="YES"
python scripts/import_data.py
```

macOS / Linux：

```bash
export CONFIRM_IMPORT=YES
python scripts/import_data.py
```

导入成功后，脚本会修复 PostgreSQL sequence，避免后续新增记录出现主键冲突。

## Cloudflare R2 上传文件迁移

如果本地已有上传文件，例如头像、帖子图片、评论图片、活动图片、圈子图片、私信图片或商家认证材料，需要把 `app/static/uploads/` 迁移到 R2，并把数据库中的旧本地路径改成 R2 URL。

迁移脚本：

```text
scripts/migrate_uploads_to_r2.py
```

### 1. 配置环境变量

PowerShell 示例：

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
$env:R2_ACCOUNT_ID="your-account-id"
$env:R2_BUCKET_NAME="your-bucket"
$env:R2_ACCESS_KEY_ID="your-access-key-id"
$env:R2_SECRET_ACCESS_KEY="your-secret-access-key"
$env:R2_PUBLIC_BASE_URL="https://assets.example.com"
```

macOS / Linux 示例：

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
export R2_ACCOUNT_ID="your-account-id"
export R2_BUCKET_NAME="your-bucket"
export R2_ACCESS_KEY_ID="your-access-key-id"
export R2_SECRET_ACCESS_KEY="your-secret-access-key"
export R2_PUBLIC_BASE_URL="https://assets.example.com"
```

### 2. 先执行 dry-run

默认模式就是 dry-run，不会真正上传，也不会改数据库。

```bash
python scripts/migrate_uploads_to_r2.py
```

检查输出中的内容：

- 扫描到多少文件。
- 计划上传到哪个 bucket 和 key。
- 计划更新多少条数据库记录。
- 示例 R2 URL 是否正确。

### 3. 确认无误后执行真实迁移

PowerShell：

```powershell
$env:CONFIRM_R2_MIGRATION="YES"
python scripts/migrate_uploads_to_r2.py
```

macOS / Linux：

```bash
export CONFIRM_R2_MIGRATION=YES
python scripts/migrate_uploads_to_r2.py
```

脚本会：

1. 上传 `app/static/uploads/` 下支持的图片文件到 R2。
2. 将数据库文本字段中的旧本地上传路径替换为 R2 公开 URL。
3. 事务提交数据库更新。
4. 保留本地文件，不会自动删除。

### 4. 迁移后验证

- 打开用户头像、活动图、圈子图、帖子图、评论图和私信图相关页面。
- 检查图片 URL 是否以 `R2_PUBLIC_BASE_URL` 开头。
- 在 Render 环境中上传一张新图片，确认新文件直接进入 R2。

## Render 部署后检查清单

| 检查项 | 预期结果 |
|---|---|
| Render build | `pip install -r requirements.txt` 成功 |
| Render start | `gunicorn wsgi:app` 成功启动 |
| 首页 | `/` 能打开 |
| 数据库 | Neon 中能看到业务表和数据 |
| 上传 | 新上传图片保存到 R2 |
| 登录注册 | Session 和 Cookie 正常 |
| 管理员 | 管理后台权限正常 |
| 静态资源 | CSS、JS、favicon 和本地静态图片正常加载 |

## 常见问题

| 问题 | 可能原因 | 处理方式 |
|---|---|---|
| Render 启动失败 | Start Command 写错 | 使用 `gunicorn wsgi:app` |
| 数据库连接失败 | `DATABASE_URL` 错误或 Neon 权限问题 | 重新复制 Neon 连接串，确认 `sslmode=require` |
| 导入脚本提示目标库已有数据 | Neon 已有业务数据 | 确认后设置 `CONFIRM_IMPORT=YES` |
| 上传时报缺少 R2 环境变量 | Render 没有配置完整 `R2_*` | 按环境变量表补齐 |
| 图片上传成功但无法访问 | `R2_PUBLIC_BASE_URL` 或 R2 公开访问未配置 | 检查 public bucket/custom domain 设置 |
| 本地运行上传到了 R2 | 本地环境配置了完整 `R2_*` | 本地开发可临时移除 R2 环境变量 |
