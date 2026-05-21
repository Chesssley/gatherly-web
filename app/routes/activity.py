from flask import Blueprint, render_template

from app.models import activities

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/")
def index():
    """
    首页路由。
    TODO: TASK-001 首页负责人完善活动卡片展示和兴趣标签筛选。
    """
    return render_template("index.html", activities=activities)


@activity_bp.route("/activities/<int:activity_id>")
def activity_detail(activity_id):
    """
    活动详情页路由。
    TODO: TASK-002 活动详情负责人完善详情展示。
    TODO: TASK-003 报名负责人后续补充报名状态。
    """
    activity = next(
        (item for item in activities if item.get("id") == activity_id),
        activities[0]
    )
    return render_template("activity_detail.html", activity=activity)


@activity_bp.route("/activities/create")
def create_activity():
    """
    发布活动页路由。
    TODO: TASK-003 发布活动负责人补充 GET/POST 表单逻辑。
    """
    return render_template("create_activity.html")