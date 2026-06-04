# Gatherly 优化修复 Git 命令清单

以下命令默认在本地仓库根目录执行，例如：

```powershell
cd D:\Dev\GitHubProjects\gatherly-web
```

## 0. 每次开工前固定步骤

```powershell
git switch main
git pull origin main
git status
```

## 1. 把参考图片放进仓库供 Codex 读取

建议路径：

```text
docs/reference/2026-06-04-optimization/
```

PowerShell 示例：

```powershell
New-Item -ItemType Directory -Force docs\reference\2026-06-04-optimization
Copy-Item -Recurse .\gatherly_codex_reference_pack\* docs\reference\2026-06-04-optimization\
```

只把这些文件作为参考资料，不要在网页里直接引用这些 Meetup 截图。

提交参考资料（可选，若仓库不适合保存第三方截图，则不要提交，只本地给 Codex 使用）：

```powershell
git switch -c docs/codex-reference-20260604
git add docs/reference/2026-06-04-optimization
git commit -m "docs(DOC-OPT): 添加 6.4 优化参考图与 Codex 任务说明"
git push -u origin docs/codex-reference-20260604
```

## 2. BUG-01 私信关注按钮状态

```powershell
git switch main
git pull origin main
git switch -c fix/bug-01-follow-button-state
# 让 Codex 只做 BUG-01，并完成本地自测
git status
git add app/routes app/templates app/static/js app/static/css
git commit -m "fix(BUG-01): 更新私信关注按钮状态"
git push -u origin fix/bug-01-follow-button-state
```

## 3. BUG-02 验证码频率限制倒计时

```powershell
git switch main
git pull origin main
git switch -c fix/bug-02-email-code-countdown
# 让 Codex 只做 BUG-02，并完成本地自测
git status
git add app/routes/auth.py app/templates app/static/js app/static/css
git commit -m "fix(BUG-02): 优化验证码频率限制倒计时提示"
git push -u origin fix/bug-02-email-code-countdown
```

## 4. ENH-01/ENH-02/UI-02 个人主页分页、搜索、隐藏邮箱

```powershell
git switch main
git pull origin main
git switch -c enhance/enh-01-profile-pagination-search
# 让 Codex 只做个人主页相关优化
git status
git add app/routes app/templates app/static/js app/static/css
git commit -m "feat(ENH-01): 优化个人主页分页和搜索界面"
git push -u origin enhance/enh-01-profile-pagination-search
```

## 5. UI-03 消息系统 UI 与详情已读

```powershell
git switch main
git pull origin main
git switch -c ui/ui-03-message-read-layout
# 让 Codex 只做消息系统 UI 和已读状态
git status
git add app/routes app/templates app/static/js app/static/css
git commit -m "fix(UI-03): 优化消息系统排版并标记详情已读"
git push -u origin ui/ui-03-message-read-layout
```

## 6. UI-04 未登录首页重构

```powershell
git switch main
git pull origin main
git switch -c ui/ui-04-guest-homepage
# 让 Codex 只做未登录首页
git status
git add app/templates/index.html app/static/css app/static/js app/static/images
# 如果首页路由也需要区分登录状态，再加入实际 route 文件：git add app/routes/xxx.py
git commit -m "style(UI-04): 重构未登录首页视觉与加入聚场入口"
git push -u origin ui/ui-04-guest-homepage
```

## 7. UI-05 已登录首页重构

```powershell
git switch main
git pull origin main
git switch -c ui/ui-05-logged-homepage
# 让 Codex 只做已登录首页
git status
git add app/templates/index.html app/static/css app/static/js app/static/images
# 如果首页路由需要补充活动/圈子数据，再加入实际 route 文件：git add app/routes/xxx.py
git commit -m "style(UI-05): 按参考图重构已登录首页"
git push -u origin ui/ui-05-logged-homepage
```

## 8. US-10-01 登录注册忘记密码弹窗化

```powershell
git switch main
git pull origin main
git switch -c feat/us-10-01-auth-modals
# 让 Codex 只做登录/注册/忘记密码弹窗，不做多步骤 onboarding
git status
git add app/routes/auth.py app/templates app/static/js app/static/css
git commit -m "feat(US-10-01): 重构登录注册忘记密码弹窗"
git push -u origin feat/us-10-01-auth-modals
```

## 9. US-10-02 注册验证码与多步骤 onboarding

```powershell
git switch main
git pull origin main
git switch -c feat/us-10-02-registration-onboarding
# 让 Codex 只做验证码通过后的注册步骤
git status
# 如果没有改数据库：
git add app/routes/auth.py app/templates app/static/js app/static/css
# 如果改了 models.py，必须同时提交 migrations：git add app/models.py migrations
git commit -m "feat(US-10-02): 增加注册验证码与新用户引导流程"
git push -u origin feat/us-10-02-registration-onboarding
```

## 10. PR 创建后必须写的内容

```markdown
## 关联 Issue
Closes #<GitHub Issue 编号>

## 本次完成内容
- 

## 自测情况
- [ ] 本地可以运行
- [ ] 相关页面无报错
- [ ] 移动端/窄屏无明显溢出

## 主要修改文件
- 

## 截图
- 

## 需要 Review 的重点
- 
```
