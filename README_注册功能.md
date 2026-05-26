# Gatherly 注册功能实现

## 📋 功能概述
已实现用户故事：**作为游客，我想注册一个 Gatherly 账号，以便使用报名、发帖和个人主页等功能。**

## ✅ 验收标准完成情况

| 验收标准 | 实现状态 | 说明 |
|----------|----------|------|
| 用户可以进入注册页面 | ✅ 完成 | 访问 `/register` 即可 |
| 注册表单包含用户名、邮箱、密码和确认密码 | ✅ 完成 | 使用 Flask-WTF 表单 |
| 用户可以提交注册信息 | ✅ 完成 | POST `/register` 处理 |
| 注册成功后用户信息能够保存 | ✅ 完成 | 密码加密存储到 SQLite |
| 注册失败时有基本错误提示 | ✅ 完成 | 表单验证 + Flash 消息 |

## 🗂️ 新增文件

### 1. `app/forms.py`
- **RegistrationForm** 类：注册表单定义
- 字段：用户名、邮箱、密码、确认密码、提交按钮
- 验证器：必填、长度、邮箱格式、密码一致性
- 自定义验证：用户名/邮箱重复检查

### 2. `app/routes/auth.py`（已更新）
- **GET `/register`**：渲染注册页面
- **POST `/register`**：处理注册逻辑
- 密码加密：`werkzeug.security.generate_password_hash`
- 数据库操作：`User` 模型插入
- 错误处理：事务回滚 + Flash 消息

### 3. `app/templates/register.html`（已更新）
- 继承 `base.html` 保持统一布局
- 表单字段渲染 + 错误提示
- 样式使用 `.form-card`、`.form-input` 等

### 4. `app/static/css/style.css`（已追加）
- `.form-label`、`.form-input`：表单样式
- `.form-error`：错误提示样式
- `.flash-msg`：成功/错误消息样式

### 5. `app/templates/base.html`（已更新）
- 添加 Flash 消息渲染区域

## 🔄 依赖更新

`requirements.txt` 新增：
- `Flask-WTF`：表单框架 + CSRF 保护
- `Werkzeug`：密码哈希（Flask 自带，但显式声明）

## 🚀 部署步骤

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 初始化数据库
```bash
python init_db.py
```

### 3. 运行应用
```bash
python run.py
```

### 4. 访问注册页面
打开浏览器访问：`http://localhost:5000/register`

## 📊 数据库结构

注册功能使用现有的 `User` 模型：
```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # 加密存储
    role = db.Column(db.String(20), default="user", nullable=False)
    trust_score = db.Column(db.Integer, default=100, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
```

## 🧪 测试用例

### 成功注册
1. 访问 `/register`
2. 输入：用户名 `testuser`、邮箱 `test@example.com`、密码 `123456`、确认密码 `123456`
3. 点击"注册"
4. 预期：跳转到登录页，显示"注册成功！现在可以登录了。"

### 验证失败
1. **密码不一致**：密码 `123456`、确认密码 `123457` → 提示"两次输入的密码不一致"
2. **密码太短**：密码 `123` → 提示"密码长度不能少于 6 个字符"
3. **邮箱格式错误**：邮箱 `test` → 提示"请输入有效的邮箱地址"
4. **用户名重复**：使用已存在的用户名 → 提示"该用户名已被注册"
5. **邮箱重复**：使用已存在的邮箱 → 提示"该邮箱已被注册"

## 🔧 技术要点

### 密码安全
- 使用 `werkzeug.security.generate_password_hash` 加密
- 默认算法：pbkdf2:sha256
- 自动加盐，防止彩虹表攻击

### 表单安全
- 自动 CSRF 保护（`{{ form.hidden_tag() }}`）
- 防止 SQL 注入（SQLAlchemy ORM）
- 输入验证在服务器端完成

### 用户体验
- 实时表单验证（客户端 + 服务器端）
- 清晰的错误提示
- 成功注册后自动跳转
- 保持与现有设计一致的视觉风格

## 📝 后续任务
- **TASK-004**：登录功能实现
- 邮箱验证（可选）
- 密码重置功能
- 用户个人资料编辑