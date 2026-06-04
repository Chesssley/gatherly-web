# Gatherly 2026-06-04 优化修复 Codex 参考包

本包用于把《6.4项目优化计划1.docx》中的参考图和任务拆分交给 Codex。建议把本文件夹放到仓库的：

```text
docs/reference/2026-06-04-optimization/
```

> 注意：这些图片只作为 UI 参考，不要直接作为网站素材放到 `app/static/` 对外展示；实际页面应使用 Gatherly 自己的中文文案、真实活动图和统一样式。

## 参考图对应关系

| 文件 | 用途 |
|---|---|
| `fig01_profile_follow_status_pagination.png` | 个人主页粉丝/已关注列表：按钮状态、搜索与分页参考 |
| `fig02_notification_center_read_status.png` | 消息/通知中心 UI 与已读状态参考 |
| `fig03_current_logged_home_problem.png` | 当前已登录首页存在的问题参考 |
| `fig04_meetup_guest_home_reference.png` | 未登录首页整体参考：顶部搜索、中间主文案、四周插图氛围 |
| `fig05_meetup_login_modal_reference.png` | 登录弹窗参考 |
| `fig06_meetup_signup_modal_reference.png` | 注册入口弹窗参考 |
| `fig07_meetup_finish_signup_modal_reference.png` | 注册填写信息弹窗参考 |
| `fig08_meetup_finish_signup_full_reference.png` | 注册完成信息页：左侧表单 + 右侧插图参考 |
| `fig09_signup_purpose_step_reference.png` | 注册步骤：选择使用目的 |
| `fig10_signup_birthdate_step_reference.png` | 注册步骤：生日/年龄 |
| `fig11_signup_gender_step_reference.png` | 注册步骤：性别/偏好 |
| `fig12_signup_interests_step_reference.png` | 注册步骤：兴趣标签 |
| `fig13_signup_groups_step_reference.png` | 注册步骤：推荐圈子/完成前推荐 |
| `fig14_meetup_logged_home_reference.png` | 已登录首页最终参考 |
| `contact_sheet.jpg` | 全部参考图总览 |

## 给 Codex 的总约束

1. 项目技术栈保持 Flask + Jinja2 + HTML/CSS + 原生 JS，不引入 Vue、React、Bootstrap。
2. 不要直接改 `main`，一个任务一个分支，一个分支一个 PR。
3. 不要上传 `.env`、数据库备份、真实密钥、`venv/`、`__pycache__/`。
4. 涉及 `models.py` 或数据库字段时，必须先说明原因，并补充 migration；纯 UI 优化不要改数据库。
5. 不要照搬 Meetup 英文文案；页面文案使用中文，品牌统一为「聚场 / Gatherly」。
6. 不要删除已有 class/id，避免破坏现有 JS 和路由。
7. 每次修改后运行本地项目并检查相关页面；PR 描述中必须写自测结果和截图。
