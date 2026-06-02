# 本地运行与部署说明

本文档说明 Gatherly Web 的本地运行、环境变量、数据库初始化和部署注意事项。

## 运行环境

建议使用：

- Python 3.10 或更新版本。
- Windows PowerShell、macOS Terminal 或 Linux shell。
- SQLite，本地数据库由 Flask/SQLAlchemy 创建在 `instance/gatherly.db`。

项目依赖以 [../requirements.txt](../requirements.txt) 为准：

```text
Flask>=3.0
Flask-SQLAlchemy
Flask-WTF
Werkzeug
email-validator
```

## 1. 获取代码

Windows PowerShell 和通用命令相同：

```bash
git clone https://github.com/Chesssley/gatherly-web.git
cd gatherly-web
```

## 2. 创建虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 阻止脚本执行，可临时调整当前用户策略：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. 安装依赖

Windows PowerShell：

```powershell
pip install -r requirements.txt
```

macOS / Linux：

```bash
pip install -r requirements.txt
```

## 4. 设置环境变量

本地开发可以不设置邮件服务，默认使用 console provider。建议至少设置 `SECRET_KEY`。

Windows PowerShell：

```powershell
$env:SECRET_KEY = "replace-with-a-local-development-secret"
$env:EMAIL_PROVIDER = "console"
```

macOS / Linux：

```bash
export SECRET_KEY="replace-with-a-local-development-secret"
export EMAIL_PROVIDER="console"
```

## 真实环境变量清单

以下变量均来自当前代码实际读取：

| 变量 | 读取位置 | 说明 |
| --- | --- | --- |
| `SECRET_KEY` | `app/__init__.py`、`app/utils/email_verification.py` | Flask session 和验证码哈希密钥 |
| `APP_ENV` | `app/__init__.py` | 判断生产环境 |
| `FLASK_ENV` | `app/__init__.py` | 判断生产环境 |
| `ENV` | `app/__init__.py` | 判断生产环境 |
| `SESSION_COOKIE_SECURE` | `app/__init__.py` | 是否强制安全 Cookie |
| `EMAIL_PROVIDER` | `app/utils/email_verification.py` | `console`、`brevo` 或 `smtp` |
| `EMAIL_API_TIMEOUT` | `app/utils/email_verification.py` | Brevo API 请求超时秒数 |
| `BREVO_API_KEY` | `app/utils/email_verification.py` | Brevo API Key |
| `BREVO_SENDER_EMAIL` | `app/utils/email_verification.py` | Brevo 发件邮箱 |
| `BREVO_SENDER_NAME` | `app/utils/email_verification.py` | Brevo 发件人名称 |
| `MAIL_SERVER` | `app/utils/email_verification.py` | SMTP 服务器 |
| `MAIL_PORT` | `app/utils/email_verification.py` | SMTP 端口 |
| `MAIL_USERNAME` | `app/utils/email_verification.py` | SMTP 用户名 |
| `MAIL_PASSWORD` | `app/utils/email_verification.py` | SMTP 密码 |
| `MAIL_USE_TLS` | `app/utils/email_verification.py` | 是否启用 SMTP TLS |
| `MAIL_DEFAULT_SENDER` | `app/utils/email_verification.py` | SMTP 默认发件人 |
| `ADMIN_USERNAME` | `init_db.py` | 初始化管理员用户名 |
| `ADMIN_EMAIL` | `init_db.py` | 初始化管理员邮箱 |
| `ADMIN_PASSWORD` | `init_db.py` | 初始化管理员密码 |

不要把真实密钥、邮箱密码、API Key 或 `.env` 文件提交到 Git。

## 5. 初始化数据库

```bash
python init_db.py
```

该命令会：

- 创建数据库表。
- 执行当前代码中的 SQLite schema 兼容处理。
- 同步系统同好圈。
- 写入 demo 活动数据。
- 如果设置了 `ADMIN_USERNAME`、`ADMIN_EMAIL`、`ADMIN_PASSWORD`，则创建或更新管理员账号。

创建管理员示例：

Windows PowerShell：

```powershell
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_EMAIL = "admin@example.invalid"
$env:ADMIN_PASSWORD = "replace-with-a-strong-password"
python init_db.py
```

macOS / Linux：

```bash
export ADMIN_USERNAME="admin"
export ADMIN_EMAIL="admin@example.invalid"
export ADMIN_PASSWORD="replace-with-a-strong-password"
python init_db.py
```

## 6. 启动本地服务

```bash
python run.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

## 邮件服务配置

### 本地 console 模式

```text
EMAIL_PROVIDER=console
```

验证码会打印到应用控制台，适合本地开发。

### Brevo 模式

```text
EMAIL_PROVIDER=brevo
BREVO_API_KEY=your_brevo_api_key
BREVO_SENDER_EMAIL=verified-sender@example.com
BREVO_SENDER_NAME=Gatherly
EMAIL_API_TIMEOUT=15
```

适合部署环境，特别是不能直接使用外部 SMTP 的平台。

### SMTP 模式

```text
EMAIL_PROVIDER=smtp
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USERNAME=your_smtp_username
MAIL_PASSWORD=your_smtp_password
MAIL_USE_TLS=true
MAIL_DEFAULT_SENDER=Gatherly <no-reply@example.com>
```

## PythonAnywhere 部署说明

当前项目是标准 Flask 应用，`run.py` 中暴露了 `app` 对象，可按 PythonAnywhere 的 Flask 项目方式部署。

基本步骤：

1. 在 PythonAnywhere 拉取仓库。
2. 创建 virtualenv。
3. 安装依赖：`pip install -r requirements.txt`。
4. 设置环境变量，至少包括 `SECRET_KEY`、`EMAIL_PROVIDER` 和邮件服务配置。
5. 执行 `python init_db.py` 初始化数据库。
6. 在 WSGI 文件中导入 Flask app。

WSGI 示例：

```python
import os
import sys

project_home = "/home/yourname/gatherly-web"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["SECRET_KEY"] = "replace-with-production-secret"
os.environ["EMAIL_PROVIDER"] = "brevo"
os.environ["BREVO_API_KEY"] = "set-on-host-only"
os.environ["BREVO_SENDER_EMAIL"] = "verified-sender@example.com"

from run import app as application
```

生产环境建议：

- 使用 HTTPS。
- 设置强 `SECRET_KEY`。
- 设置 `APP_ENV=production` 或 `SESSION_COOKIE_SECURE=true`。
- 不提交或上传 `.env`、本地数据库、虚拟环境和缓存目录。
- 定期备份 `instance/gatherly.db` 和上传文件。

## 常见问题

### 找不到依赖

确认虚拟环境已激活，再执行：

```bash
pip install -r requirements.txt
```

### 数据库不存在

执行：

```bash
python init_db.py
```

### 邮箱验证码收不到

本地优先使用：

```text
EMAIL_PROVIDER=console
```

部署环境检查 Brevo 或 SMTP 变量是否完整。

