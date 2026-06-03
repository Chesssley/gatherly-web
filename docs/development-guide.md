# 开发指南

最后更新时间：2026-06-04

本文面向 Gatherly Web 组员，说明本地开发、分支、提交、PR 和自测流程。当前技术栈固定为 Flask + Jinja2 + HTML/CSS/原生 JavaScript，不引入 React、Vue、Bootstrap、新数据库或新依赖。

## 本地运行

### 1. 创建虚拟环境

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

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python init_db.py
```

如果需要示例数据：

```bash
python seed_data.py
```

### 4. 启动 Flask

```bash
python run.py
```

浏览器打开：

```text
http://127.0.0.1:5000/
```

## 常见目录

| 路径 | 用途 |
|---|---|
| `app/routes/activity.py` | 首页、搜索、活动详情、发布、报名、收藏、评论、评分 |
| `app/routes/auth.py` | 注册、登录、账号设置、验证码、密码和邮箱 |
| `app/routes/circle.py` | 同好圈、成员、帖子、评论、互动 |
| `app/routes/profile.py` | 个人主页、关注、附近的人、个人内容 |
| `app/routes/admin.py` | 管理员后台 |
| `app/templates/` | Jinja2 页面模板 |
| `app/static/css/style.css` | 全站主要样式 |
| `app/static/js/` | 原生 JS 交互 |
| `app/models.py` | 数据库模型 |
| `docs/` | 项目文档 |

## 分支命名

```text
feat/us-04-01-create-activity-page
fix/bug-02-clean-test-circles
docs/doc-04-reorganize-docs-er
ui/ui-01-card-style
enh/enh-03-auto-dismiss-flash
```

## Commit 命名

```text
type(ISSUE-ID): short description
```

示例：

```text
feat(US-04-01): add activity creation page
fix(BUG-02): clean invalid test circles
docs(DOC-04): reorganize documentation and ER diagram
style(UI-01): align activity card spacing
```

## PR 模板

```markdown
## Summary
- 
- 

## Changed Files
- 
- 

## Verification
- [ ] python -m compileall app
- [ ] Flask app factory loads
- [ ] Manually checked affected page

## Screenshots

Add screenshots if UI changed.

## Related Issue

Closes #
```

## 自测清单

基础检查：

```bash
python -m compileall app
python -c "from app import create_app; app = create_app(); print('app loaded')"
```

页面检查：

- 首页 `/` 能打开。
- `/login` 和 `/register` 能打开。
- 首页活动卡片能进入 `/activity/<id>`。
- 登录用户能进入 `/activities/create`。
- `/circles` 或 `/circle` 能打开。
- `/profile/` 未登录时按预期跳转或提示。
- 管理员页面普通用户不能访问。

文档检查：

- Markdown 标题层级清晰。
- 相对链接能从 GitHub 正常点击。
- 文档内容和当前真实代码一致。
- 数据库字段以 `app/models.py` 为准。

## 常见错误处理

| 问题 | 可能原因 | 处理方式 |
|---|---|---|
| `ModuleNotFoundError: flask` | 没有激活虚拟环境或未安装依赖 | 激活 `.venv`，运行 `pip install -r requirements.txt` |
| 数据库表不存在 | 没有初始化数据库 | 运行 `python init_db.py` |
| 端口被占用 | 5000 端口已有程序 | 关闭占用程序，或临时用 `flask run --port 5001` |
| 页面样式没有变化 | 浏览器缓存 | 强制刷新，或打开无痕窗口 |
| 登录状态异常 | 本地 cookie/session 旧数据 | 退出登录、清理浏览器缓存或重启服务 |
| 合并冲突 | 多人改了同一文件 | 先沟通冲突范围，只解决自己的改动，不要覆盖他人内容 |

## 高风险改动

以下文件改动前必须确认：

- `app/models.py`
- `app/__init__.py`
- `run.py`
- `requirements.txt`
- `.gitignore`

如果确实需要改模型，必须同时更新：

- [database-design.md](database-design.md)
- [er-diagram.md](er-diagram.md)
- 数据库迁移或初始化说明
