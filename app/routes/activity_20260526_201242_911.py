from flask import Blueprint, render_template, abort

from app.models import db, Activity, Registration, activities

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/")
def index():
    """
    首页路由。
    TODO: TASK-001 首页负责人完善活动卡片展示和兴趣标签筛选。
    """
    return render_template("index.html", activities=activities)


# US-03-01: 活动详情页路由 —— 用户查看活动完整介绍
# US-03-03: 新增报名人数和报名状态数据
@activity_bp.route("/activity/<int:activity_id>")
def activity_detail(activity_id):
    """
    活动详情页。
    根据 activity_id 从 activities 列表中查找对应活动。
    找不到则返回 404。
    同时查询 DB 获取报名人数和报名上限。
    """
    activity = next((a for a in activities if a.get("id") == activity_id), None)
    if activity is None:
        abort(404)

    # US-03-03: 查询报名人数
    registration_count = Registration.query.filter_by(activity_id=activity_id).count()

    # 查询或初始化活动DB记录
    db_activity = Activity.query.get(activity_id)
    if db_activity is None:
        db_activity = Activity(
            id=activity_id,
            title=activity.get("title", ""),
            description=activity.get("description") or activity.get("detail", ""),
            location=activity.get("location", ""),
            max_participants=30,
        )
        db.session.add(db_activity)
        db.session.commit()

    max_participants = db_activity.max_participants
    user_registered = False

    return render_template(
        "activity_detail.html",
        activity=activity,
        registration_count=registration_count,
        max_participants=max_participants,
        user_registered=user_registered,
    )


@activity_bp.route("/activities/create")
def create_activity():
    """
    发布活动页路由。
    TODO: TASK-003 发布活动负责人补充 GET/POST 表单逻辑。
    """
    return render_template("create_activity.html")