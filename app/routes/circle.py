from types import SimpleNamespace

from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from app.models import db, Circle, Post
from app.routes.activity import OFFICIAL_INTEREST_TAGS

circle_bp = Blueprint("circle", __name__)

_CIRCLE_DESCRIPTIONS = {
    "影像摄影": "聚合胶片摄影、相机维修、街头摄影、摄影展和桌面摄影等影像爱好者。",
    "运动户外": "覆盖骑行、徒步、露营、夜跑、飞盘、攀岩等线下运动与轻户外约伴。",
    "咖啡茶饮": "连接手冲咖啡、咖啡拉花、茶会品鉴和咖啡店探访爱好者。",
    "阅读出版": "围绕独立出版、读书会、二手书交换、写作交流和书店探访展开。",
    "手作艺术": "收纳陶艺、插画手账、手帐拼贴、香薰调香和其他手作体验。",
    "音乐演出": "发现 Livehouse、音乐节、黑胶唱片试听和小型音乐现场。",
    "观影戏剧": "组织观影交流、剧本围读、即兴戏剧和展演后的线下讨论。",
    "城市探索": "发起城市漫步、旧物市集、古着穿搭、博物馆看展和本地探访。",
    "游戏桌游": "包含桌游组局、独立游戏试玩、模型手办交流和轻松联机活动。",
    "科技数码": "面向开源技术、数码工具、创客实践和技术主题线下分享。",
    "美食烘焙": "聚合本地美食、烘焙试吃、食谱交流和周末探店计划。",
    "公益志愿": "连接社区服务、公益行动、环保活动和志愿者线下协作。",
}

_ACTIVE_LEVELS = ["高活跃", "稳定活跃", "新兴活跃"]


def _build_mock_circles():
    circles = []
    for index, tag in enumerate(OFFICIAL_INTEREST_TAGS, start=1):
        member_count = 96 + index * 17 + (index % 5) * 23
        post_count = 12 + index * 3 + (index % 4) * 5
        circles.append(
            {
                "id": index,
                "name": f"{tag}同好圈",
                "tag": tag,
                "description": _CIRCLE_DESCRIPTIONS[tag],
                "active_level": _ACTIVE_LEVELS[index % len(_ACTIVE_LEVELS)],
                "member_count": member_count,
                "post_count": post_count,
                # 兼容已有发帖页或旧模板中可能使用的示例字段。
                "members": member_count,
                "activity_count": 2 + index % 7,
            }
        )
    return circles


mock_circles = _build_mock_circles()


def _get_circle(circle_id):
    circle = Circle.query.get(circle_id)
    if circle is not None:
        return circle

    mock_circle = next((item for item in mock_circles if item["id"] == circle_id), None)
    if mock_circle is None:
        return None
    return SimpleNamespace(**mock_circle)


@circle_bp.route("/circles")
def circles():
    """
    用户浏览兴趣圈子列表页面路由。
    US-07-01: 同好圈标签与首页官方兴趣标签保持一致。
    """
    return render_template("circle.html", circles=mock_circles)


@circle_bp.route("/circle")
def circle_list():
    """兼容旧的同好圈入口，逻辑同 circles。"""
    return circles()


@circle_bp.route("/circle/<int:circle_id>/post", methods=["GET", "POST"])
def create_post(circle_id):
    """
    发布圈子帖子路由。
    US-08-01: 登录用户发布圈子帖子功能。
    """
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login", next=request.url))

    circle = _get_circle(circle_id)
    if circle is None:
        flash("圈子不存在或已被删除", "error")
        return redirect(url_for("circle.circles"))

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
        user_id=user_id,
        circle_id=circle_id
    )

    try:
        db.session.add(post)
        db.session.commit()
        flash("帖子发布成功！", "success")
        return redirect(url_for("circle.circles"))
    except Exception as e:
        db.session.rollback()
        flash("发布失败，请稍后重试", "error")
        return render_template("create_post.html", circle=circle)
