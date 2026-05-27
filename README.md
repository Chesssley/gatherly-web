# Gatherly Web

Gatherly Web 是一个面向小众兴趣爱好者的线下活动聚合与同好匹配平台原型。项目目标是帮助用户发现本地兴趣活动、查看活动详情、注册登录、报名活动，并通过同好圈找到兴趣相近的人。

本项目技术栈固定为 Flask + Jinja2 + HTML/CSS/原生 JavaScript。依赖说明以 `requirements.txt` 为准，不使用 React、Vue、Bootstrap、PDM 或 Poetry。

## 核心功能

- 首页活动流展示和兴趣标签筛选。
- 活动详情查看，展示地点、时间、人数上限和报名状态。
- 用户注册、登录、退出和基础登录态判断。
- 登录用户可报名活动，并避免重复报名、过期报名和满员报名。
- 发布活动页面和后台管理页面占位。
- 同好圈列表页面，用于后续兴趣圈和帖子功能扩展。

## 项目结构

```text
gatherly-web/
├── app/
│   ├── __init__.py
│   ├── forms.py
│   ├── models.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── activity.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   └── circle.py
│   ├── static/
│   │   ├── css/style.css
│   │   ├── images/
│   │   └── js/main.js
│   └── templates/
├── docs/
│   ├── git-guide.md
│   ├── issue-rules.md
│   ├── meeting-notes.md
│   ├── product-backlog.md
│   ├── register-feature.md
│   ├── style-guide.md
│   ├── meeting-notes/
│   └── screenshots/
├── instance/
│   └── gatherly.db        # 本地生成，不提交 Git
├── scripts/
├── init_db.py
├── requirements.txt
├── run.py
└── README.md
```

## 安装运行步骤

1. 创建并激活虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 初始化数据库：

```bash
python init_db.py
```

数据库文件会生成在 Flask instance 目录中，当前为 `instance/gatherly.db`。该文件只用于本地开发，不提交到 Git。

4. 启动应用：

```bash
python run.py
```

5. 在浏览器访问：

```text
http://127.0.0.1:5000
```

## 主要路由

| 路由 | 说明 |
|---|---|
| `/` | 首页活动流 |
| `/activity/<id>` | 活动详情页 |
| `/activity/<id>/register` | 活动报名接口 |
| `/activities/create` | 发布活动页 |
| `/login` | 登录页 |
| `/register` | 注册页 |
| `/logout` | 退出登录 |
| `/circles` | 同好圈列表页 |
| `/admin` | 后台管理占位页 |

## GitHub 协作流程

1. 每个需求或修复先创建 GitHub Issue，并设置 Label、Milestone 和 Project Status。
2. 开发前从 `main` 拉取最新代码。
3. 每个任务使用独立分支，例如 `feature/register-form`、`fix/activity-register-limit`。
4. 本地完成修改后执行基本验证，再提交 commit。
5. 推送分支到 GitHub，并创建 Pull Request。
6. PR 说明中关联 Issue，写清楚修改内容、验证方式和影响范围。
7. 代码审查通过后再合并到 `main`。
8. 合并后可删除已合并的本地和远程分支。

详细说明见 [docs/git-guide.md](docs/git-guide.md) 和 [docs/issue-rules.md](docs/issue-rules.md)。

## 团队分工

| 角色 | 主要职责 |
|---|---|
| 组长 / Scrum Master | 项目规划、仓库管理、Issue 和 PR 审查、Sprint 进度维护 |
| 首页前端负责人 | 首页活动流、活动卡片、兴趣标签和移动端布局 |
| 活动页面负责人 | 活动详情页、发布活动页、报名按钮和活动信息展示 |
| 用户系统负责人 | 注册、登录、退出、登录态和个人资料基础能力 |
| 活动业务负责人 | 活动报名、人数上限、满员提示和报名记录 |
| 数据库负责人 | 用户、活动、报名、同好圈、帖子、评分等模型设计 |
| 文档测试负责人 | README、会议记录、截图、功能测试和演示材料 |

## 已完成与待优化功能

已完成：

- Flask 应用基础结构。
- Jinja2 模板和公共静态资源目录。
- 首页、活动详情、发布活动、登录、注册、同好圈、后台占位页面。
- 用户注册表单、密码哈希存储和基础错误提示。
- 登录、退出和基础 session 登录态。
- 活动报名基础逻辑，包括重复报名、过期活动和满员检查。
- Product Backlog、会议记录、Git 协作规则和页面风格规范文档。

待优化：

- 完善活动发布的表单提交和数据库保存逻辑。
- 完善个人主页、兴趣标签和同好圈帖子功能。
- 增加活动评分、履约评分和信任机制。
- 补充更系统的测试用例和演示截图。
- 统一数据库初始化脚本输出编码，避免中文控制台乱码。
