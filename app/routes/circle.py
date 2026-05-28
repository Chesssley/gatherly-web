from flask import Blueprint, abort, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.models import db, Circle, Post

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


@circle_bp.route("/circle/<int:circle_id>/post", methods=["GET", "POST"])
@login_required
def create_post(circle_id):
    """
    发布圈子帖子路由。
    US-08-01: 登录用户发布圈子帖子功能。
    """
    circle = Circle.query.get(circle_id)
    if circle is None:
        abort(404)

    if request.method == "GET":
        return render_template("create_post.html", circle=circle)

    # POST 请求处理
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    post_type = request.form.get("type", "share").strip()

    # 验证字段
    if not title or not content:
        flash("标题和内容不能为空", "error")
        return render_template("create_post.html", circle=circle)
    if len(title) > 100:
        flash("标题长度不能超过100字符", "error")
        return render_template("create_post.html", circle=circle)

    # 创建帖子对象
    post = Post(
        title=title,
        content=content,
        type=post_type,
        user_id=current_user.id,
        circle_id=circle_id
    )

    try:
        db.session.add(post)
        db.session.commit()
        flash("帖子发布成功！", "success")
        return redirect(url_for("circle.circle_detail", circle_id=circle_id))
    except Exception as e:
        db.session.rollback()
        flash("发布失败，请稍后重试", "error")
        return render_template("create_post.html", circle=circle)
