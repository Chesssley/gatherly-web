from flask import Blueprint, render_template, abort

from app.models import activities

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/")
def index():
    """
    首页路由。
    TODO: TASK-001 首页负责人完善活动卡片展示和兴趣标签筛选。
    """
    return render_template("index.html", activities=activities)


# US-03-01: 活动详情页路由 —— 用户查看活动完整介绍
@activity_bp.route("/activity/<int:activity_id>")
def activity_detail(activity_id):
    """
    活动详情页。
    根据 activity_id 从 activities 列表中查找对应活动。
    找不到则返回 404。
    """
    activity = next((a for a in activities if a.get("id") == activity_id), None)
    if activity is None:
        abort(404)
    return render_template("activity_detail.html", activity=activity)


@activity_bp.route("/activities/create")
def create_activity():
    """
    发布活动页路由。
    TODO: TASK-003 发布活动负责人补充 GET/POST 表单逻辑。
    """
    return render_template("create_activity.html")