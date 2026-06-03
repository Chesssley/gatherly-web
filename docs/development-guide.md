# 开发指南

最后更新：2026-06-04

本文面向 Gatherly Web 组员，说明本地开发、分支、提交、PR、自测和数据库迁移规则。当前正式线上架构是 Render + Neon PostgreSQL + Cloudflare R2 + GitHub。

## 本地运行

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

浏览器打开：

```text
http://127.0.0.1:5000/
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## 本地数据库

当前代码在未设置 `DATABASE_URL` 时会使用 SQLite fallback：`sqlite:///gatherly.db`。这只用于本地快速开发，不代表生产环境。

推荐做法：

- 普通页面和样式开发可以用 SQLite fallback。
- 数据库迁移、字段变更验证和生产一致性验证应连接 Neon。
- 使用 `.env` 保存本地环境变量，但不要提交 `.env`。
- 不要把数据库密码、R2 Secret、管理员密码写进 README 或 docs。
- 真实数据库备份不得提交 GitHub。

## 本地上传 fallback

当前代码在未配置 R2 且不是生产环境时，图片可能保存到 `app/static/uploads/`。这只是本地开发 fallback 或历史迁移来源，不是 Render 生产持久化存储。

生产环境必须配置 R2。上传图片文件本体进入 Cloudflare R2，Neon PostgreSQL 当前只保存 R2 public URL。

真实图片备份不得提交 GitHub。GitHub 只保存代码、文档、migrations 和配置模板，不保存真实用户上传图片。

## 数据库迁移

不要使用 `db.create_all()` 作为正式数据库更新方式。生产 schema 变更必须使用 Flask-Migrate / Alembic。

PowerShell 示例：

```powershell
$env:FLASK_APP='wsgi:app'
$env:DATABASE_URL='<Neon Direct URL, not the pooler URL>'
flask db migrate -m "describe schema change"
flask db upgrade
```

规则：

- `app/models.py` 是高风险文件。
- `migrations/` 是数据库版本记录，必须提交。
- 改数据库字段必须单独 PR 或在 PR 中单独清楚说明。
- 迁移时使用 Neon Direct URL，不使用 pooled URL。
- Render 运行时使用 Neon pooled URL。
- 生成 migration 后必须人工审查，确认不会误删表或误删字段。

## 环境变量

本地 `.env` 可使用占位式结构：

```text
DATABASE_URL=<local sqlite fallback or Neon Direct URL>
SECRET_KEY=<local secret>
APP_ENV=development
R2_ACCOUNT_ID=<cloudflare account id>
R2_ACCESS_KEY_ID=<r2 access key id>
R2_SECRET_ACCESS_KEY=<r2 secret access key>
R2_BUCKET_NAME=gatherly-uploads
R2_PUBLIC_BASE_URL=<r2 public base url>
EMAIL_PROVIDER=console
```

不要提交：

- `.env`
- `DATABASE_URL`
- 数据库密码
- `SECRET_KEY`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- R2 Secret
- `ADMIN_PASSWORD`
- 数据库备份
- 图片备份
- 真实用户数据
- 真实图片

密钥和密码只放 Render Environment 或本地 `.env`。GitHub 不保存真实用户数据、真实图片、数据库密码、R2 Secret、`.env`、数据库备份或图片备份。

## 常见目录

| 路径 | 用途 |
|---|---|
| `app/models.py` | SQLAlchemy 模型，高风险。 |
| `migrations/` | Alembic migration，高风险，必须随模型变更提交。 |
| `app/services/storage.py` | R2 / 本地 fallback 上传逻辑。 |
| `app/utils/upload_utils.py` | 上传校验和保存入口。 |
| `app/routes/` | Flask Blueprint 路由。 |
| `app/templates/` | Jinja2 页面模板。 |
| `app/static/css/style.css` | 全站 CSS。 |
| `app/static/js/` | 原生 JavaScript。 |
| `docs/` | 项目文档。 |

## 分支与 PR

团队流程：

1. 一个 Issue。
2. 一个分支。
3. 一个 Pull Request。
4. Review 后 merge。
5. Merge 到 `main` 后 Render 自动部署。

不要直接 push 到 `main`。

推荐分支格式：

```text
feat/us-04-01-create-activity-page
fix/bug-02-clean-test-circles
docs/doc-06-update-render-neon-r2-docs
ui/ui-01-card-style
enh/enh-03-auto-dismiss-flash
```

推荐 commit 格式：

```text
type(ISSUE-ID): short description
```

示例：

```text
docs(DOC-06): update documentation for Render Neon R2 architecture
```

## PR 模板

```markdown
## Summary
- 

## Changed Files
- 

## Database / Storage Impact
- [ ] No database schema change
- [ ] Migration included
- [ ] Upload/R2 behavior changed

## Verification
- [ ] python -m compileall app
- [ ] Flask app factory loads
- [ ] Manually checked affected page

## Related Issue
Closes #
```

## 自测清单

基础检查：

```powershell
python -m compileall app
python -c "from app import create_app; app = create_app(); print('app loaded')"
```

页面检查：

- 首页 `/` 能打开。
- `/login` 和 `/register` 能打开。
- 活动详情页能打开。
- 登录用户能进入 `/activities/create`。
- `/circles` 或 `/circle` 能打开。
- `/profile/` 未登录时按预期跳转或提示。
- 普通用户不能访问管理员页面。

文档检查：

- README 为英文。
- docs 下中文文档使用 Render + Neon PostgreSQL + Cloudflare R2 作为正式架构。
- 数据库字段以 `app/models.py` 为准。
- 图片上传策略写成 R2 存文件、数据库存 R2 public URL。

## 高风险改动

以下文件改动前必须确认影响范围：

- `app/models.py`
- `migrations/`
- `app/__init__.py`
- `app/services/storage.py`
- `app/utils/upload_utils.py`
- `requirements.txt`
- `.gitignore`

如果确实需要改模型，必须同步更新：

- [database-design.md](database-design.md)
- [er-diagram.md](er-diagram.md)
- migration 文件
- PR 中的数据库影响说明

## 常见错误

| 问题 | 可能原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: flask` | 未激活虚拟环境或未安装依赖 | 激活 `.venv`，运行 `pip install -r requirements.txt`。 |
| 表不存在 | 没有初始化本地数据库或未执行 migration | 本地可初始化；生产/Neon 使用 `flask db upgrade`。 |
| 上传失败 | R2 环境变量缺失或生产环境未配置 R2 | 补齐 Render Environment 中的 `R2_*`。 |
| 图片路径是 `/static/uploads/...` | 本地 fallback 或历史数据 | 生产数据应迁移到 R2，并保存 R2 URL。 |
| 合并冲突 | 多人改同一文件 | 只解决自己改动范围，保留他人改动。 |
