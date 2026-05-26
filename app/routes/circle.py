from flask import Blueprint, render_template

from app.models import circles

circle_bp = Blueprint("circle", __name__)


@circle_bp.route("/circles")
def circles():
    """
    同好圈页面路由。
    TODO: TASK-005 同好圈负责人完善圈子列表、圈子详情和帖子功能。
    """
    return render_template("circle.html", circles=circles)


@circle_bp.route("/circle")
def circle_list():
    """
    用户浏览兴趣圈子列表页面路由。
    US-07-01: 展示模拟兴趣圈子数据，包含圈子名称、简介、本月活动数和成员数。
    """
    mock_circles = [
        {
            "id": 1,
            "name": "胶片摄影",
            "description": "用胶片捕捉光影，分享暗房技巧与器材心得，一起慢下来感受摄影的本质。",
            "activity_count": 8,
            "member_count": 342,
        },
        {
            "id": 2,
            "name": "城市骑行",
            "description": "周末城市探索骑行，从老城区到滨江绿道，用车轮丈量城市的温度。",
            "activity_count": 12,
            "member_count": 567,
        },
        {
            "id": 3,
            "name": "手冲咖啡",
            "description": "从选豆到注水，探索手冲咖啡的无限可能，定期举办杯测与分享会。",
            "activity_count": 6,
            "member_count": 218,
        },
        {
            "id": 4,
            "name": "独立出版",
            "description": "关注独立杂志、艺术书与Zine文化，为小众创作者提供交流与展示的平台。",
            "activity_count": 4,
            "member_count": 156,
        },
        {
            "id": 5,
            "name": "桌游",
            "description": "从德式策略到美式主题，每周线下组局，欢迎新手和老玩家一起上桌。",
            "activity_count": 15,
            "member_count": 723,
        },
        {
            "id": 6,
            "name": "徒步",
            "description": "周末山野徒步，逃离城市喧嚣，用脚步发现身边的自然之美。",
            "activity_count": 10,
            "member_count": 489,
        },
        {
            "id": 7,
            "name": "音乐现场",
            "description": "聚焦本地Livehouse演出与独立音乐人，一起发现下一个打动你的声音。",
            "activity_count": 9,
            "member_count": 401,
        },
    ]
    return render_template("circle.html", circles=mock_circles)