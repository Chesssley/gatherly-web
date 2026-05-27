from flask import Blueprint, render_template

circle_bp = Blueprint("circle", __name__)

mock_circles = [
    {
        "id": 1,
        "name": "胶片摄影",
        "tag": "影像",
        "description": "用胶片捕捉光影，分享暗房技巧与器材心得，一起慢下来感受摄影的本质。",
        "members": 342,
        "activity_count": 8,
    },
    {
        "id": 2,
        "name": "城市骑行",
        "tag": "户外",
        "description": "周末城市探索骑行，从老城区到滨江绿道，用车轮丈量城市的温度。",
        "members": 567,
        "activity_count": 12,
    },
    {
        "id": 3,
        "name": "手冲咖啡",
        "tag": "生活方式",
        "description": "从选豆到注水，探索手冲咖啡的无限可能，定期举办杯测与分享会。",
        "members": 218,
        "activity_count": 6,
    },
    {
        "id": 4,
        "name": "独立出版",
        "tag": "创作",
        "description": "关注独立杂志、艺术书与 Zine 文化，为小众创作者提供交流与展示的平台。",
        "members": 156,
        "activity_count": 4,
    },
    {
        "id": 5,
        "name": "桌游",
        "tag": "游戏",
        "description": "从德式策略到美式主题，每周线下组局，欢迎新手和老玩家一起上桌。",
        "members": 723,
        "activity_count": 15,
    },
    {
        "id": 6,
        "name": "徒步",
        "tag": "自然",
        "description": "周末山野徒步，逃离城市喧嚣，用脚步发现身边的自然之美。",
        "members": 489,
        "activity_count": 10,
    },
]


@circle_bp.route("/circles")
def circles():
    """
    用户浏览兴趣圈子列表页面路由。
    US-07-01: 展示模拟兴趣圈子数据。
    """
    return render_template("circle.html", circles=mock_circles)


@circle_bp.route("/circle")
def circle_list():
    """
    兼容旧的同好圈入口。
    """
    return render_template("circle.html", circles=mock_circles)
