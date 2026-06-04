A1：BUG-01 私信关注按钮状态

BUG-01 私信关注按钮状态

Codex 提示词：

```text
当前只修复 [BUG-01] 私信系统点击关注后弹窗按钮状态问题。
目标：用户在私信系统或用户详情弹窗中点击“关注用户”后，如果后端关注成功，弹窗里的按钮立即变为“已关注”，并禁用或切换成取消关注入口，不能仍显示“关注用户”。
参考图：docs/reference/2026-06-04-optimization/reference-images/fig01_profile_follow_status_pagination.png
请先搜索项目中 follow、关注用户、已关注、message、profile、user modal 相关代码。
允许修改：消息/个人主页相关模板、对应 route、少量 JS、少量 CSS。
禁止修改：数据库字段、登录注册、首页大布局。
验收：点击关注后无需刷新即可看到“已关注”；刷新页面后状态仍正确；失败时显示错误提示。
```

