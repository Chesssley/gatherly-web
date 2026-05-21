"""
Gatherly 项目临时数据模型。

当前阶段不连接数据库，只保留最小模拟数据，方便 Flask 页面正常运行。
后续由组员根据 Issues 继续完善用户、活动、报名、圈子、帖子、评分等数据结构。
"""

# TODO: TASK-002 数据负责人完善活动数据结构
activities = [
    {
        "id": 1,
        "title": "示例活动标题",
        "category": "示例标签",
        "time": "待补充",
        "location": "待补充",
        "capacity": "待补充",
        "description": "待补充活动简介",
        "detail": "待补充活动详情",
    }
]

# TODO: TASK-005 同好圈负责人完善圈子数据结构
circles = [
    {
        "id": 1,
        "name": "示例圈子名称",
        "tag": "示例标签",
        "summary": "待补充圈子简介",
        "members": 0,
    }
]

# TODO: 后续可补充 users、registrations、posts、reviews 等模拟数据
users = []
registrations = []
posts = []
reviews = []