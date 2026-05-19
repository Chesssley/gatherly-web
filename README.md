# Gatherly

Gatherly 是一个面向小众兴趣爱好者的线下活动聚合与同好匹配平台原型。项目目标是帮助用户发现本地兴趣活动、查看活动详情、发布活动，并通过同好圈找到同频人群。

## 项目背景

现实生活中，许多小众兴趣爱好者会遇到这些问题：

- 想参加线下活动，但不知道本地哪里有相关活动；
- 有兴趣爱好，但很难找到同频同好；
- 普通社交平台信息分散，活动真实性和参与体验难以判断；
- 活动组织者缺少精准触达兴趣用户的平台。

Gatherly 希望通过“活动聚合 + 同好圈 + 信任机制”的方式，提供一个轻量、真实、低打扰的兴趣活动平台。

## 核心功能

- 首页活动流展示；
- 活动详情查看；
- 用户注册和登录页面；
- 发布线下活动页面；
- 同好圈列表页面；
- 后台管理占位页面。

## 技术栈

- 后端：Python Flask
- 前端：HTML 模板、CSS、JavaScript
- 数据：当前使用 `app/models.py` 中的模拟数据，暂未连接数据库

## 项目结构

```text
Gatherly/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── activity.py
│   │   ├── circle.py
│   │   └── admin.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── activity_detail.html
│   │   ├── create_activity.html
│   │   └── circle.html
│   └── static/
│       ├── css/
│       │   └── style.css
│       ├── js/
│       │   └── main.js
│       └── images/
├── docs/
│   ├── product-backlog.md
│   ├── meeting-notes.md
│   └── screenshots/
├── requirements.txt
├── run.py
├── README.md
└── .gitignore
```

## 本地运行

1. 创建并激活虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 启动项目：

```bash
python run.py
```

4. 在浏览器访问：

```text
http://127.0.0.1:5000
```

## 路由说明

- `/`：首页与活动卡片
- `/activities/<id>`：活动详情页
- `/activities/create`：发布活动页
- `/login`：登录页
- `/register`：注册页
- `/circles`：同好圈列表页
- `/admin`：后台管理占位页
