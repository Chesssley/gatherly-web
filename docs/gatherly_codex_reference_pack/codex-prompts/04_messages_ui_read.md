C1：消息系统 UI 与已读状态

消息系统 UI 与已读状态

```text
当前只优化消息系统 UI 和已读状态。
目标：统一消息系统的 UI 排版、文字和按钮位置；用户点击“查看详情”之后，该条消息默认变为已读状态。
参考图：fig02_notification_center_read_status.png。
请搜索 notification、message、inbox、read、unread、查看详情、全部标为已读 相关代码。
验收：消息列表排版统一；未读/已读视觉区别清晰；点击详情后数据库/后端状态变为已读；返回列表后不再显示未读。
```

