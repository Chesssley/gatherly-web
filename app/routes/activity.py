from flask import Blueprint, abort, render_template, request, session, redirect, url_for, flash
from functools import wraps
from datetime import datetime

from app.models import db, Activity, Registration, activities

def login_required(f):
    """登录态检查装饰器，未登录重定向到登录页"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("请先登录后再报名活动", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/")
def index():
    selected_tag = request.args.get("tag", "").strip()
    interest_tags = [
        "胶片摄影",
        "复古相机",
        "城市骑行",
        "公路车",
        "手冲咖啡",
        "独立出版",
        "桌游",
        "剧本围读",
        "观影交流",
        "摄影展",
        "城市漫步",
        "徒步",
        "露营",
        "飞盘",
        "羽毛球",
        "攀岩",
        "滑板",
        "夜跑",
        "音乐现场",
        "黑胶唱片",
        "旧物市集",
        "古着穿搭",
        "二手书交换",
        "书店探访",
        "博物馆看展",
        "手作体验",
        "陶艺",
        "插画手账",
        "手帐拼贴",
        "植物养护",
        "宠物社交",
        "烘焙",
        "茶饮品鉴",
        "香薰调香",
        "语言角",
        "开源技术",
        "独立游戏",
        "模型手办",
        "汉服体验",
        "天文观星",
        "即兴戏剧",
        "瑜伽冥想",
        "本地美食",
        "桌面摄影",
        "咖啡拉花",
        "街头摄影",
        "骑行路线",
        "周末约伴",
        "轻户外",
    ]
    categories = interest_tags
    visible_tag_count = 18

    if selected_tag and selected_tag in interest_tags:
        filtered_activities = [
            activity for activity in activities if activity["category"] == selected_tag
        ]
    else:
        filtered_activities = activities
        selected_tag = ""

    expand_tags_by_default = (
        bool(selected_tag)
        and interest_tags.index(selected_tag) >= visible_tag_count
    )

    # 合并真实报名人数到硬编码活动数据
    from sqlalchemy import func
    reg_counts = dict(
        db.session.query(Registration.activity_id, func.count(Registration.id))
        .group_by(Registration.activity_id)
        .all()
    )
    for act in filtered_activities:
        act["current_people"] = reg_counts.get(act["id"], 0)

    return render_template(
        "index.html",
        activities=filtered_activities,
        categories=categories,
        expand_tags_by_default=expand_tags_by_default,
        interest_tags=interest_tags,
        selected_tag=selected_tag,
        visible_tag_count=visible_tag_count,
    )


@activity_bp.route("/activity/<int:activity_id>")
def activity_detail(activity_id):
    activity = next((a for a in activities if a.get("id") == activity_id), None)
    if activity is None:
        abort(404)

    try:
        registration_count = Registration.query.filter_by(activity_id=activity_id).count()
        db_activity = Activity.query.get(activity_id)
        max_participants = db_activity.max_participants if db_activity else None
        preparation = db_activity.preparation if db_activity else None
        user_registered = False
        if "user_id" in session:
            user_registered = Registration.query.filter_by(
                user_id=session["user_id"], activity_id=activity_id
            ).first() is not None
    except Exception:
        registration_count = 0
        max_participants = None
        preparation = None
        user_registered = False

    return render_template(
        "activity_detail.html",
        activity=activity,
        registration_count=registration_count,
        max_participants=max_participants,
        preparation=preparation,
        user_registered=user_registered,
    )


@activity_bp.route("/activities/create")
def create_activity():
    return render_template("create_activity.html")

@activity_bp.route("/activity/<int:activity_id>/register", methods=["POST"])
def register_activity(activity_id):
    """活动报名路由"""
    # 检查用户是否登录，未登录则重定向到登录页并带上next参数
    if "user_id" not in session:
        flash("请先登录后再报名活动", "error")
        next_url = url_for("activity.activity_detail", activity_id=activity_id)
        return redirect(url_for("auth.login", next=next_url))

    activity = next((a for a in activities if a.get("id") == activity_id), None)
    if activity is None:
        abort(404)

    user_id = session["user_id"]

    # ===== US-05-03：重复报名检查 =====
    existing = Registration.query.filter_by(user_id=user_id, activity_id=activity_id).first()
    if existing:
        flash("您已报名该活动，无需重复报名", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 检查活动是否已过期
    db_activity = Activity.query.get(activity_id)
    if db_activity and db_activity.start_time and db_activity.start_time < datetime.utcnow():
        flash("该活动已过期，无法报名", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 检查是否已满员
    if db_activity and db_activity.max_participants is not None:
        current_count = Registration.query.filter_by(activity_id=activity_id).count()
        if current_count >= db_activity.max_participants:
            flash("该活动已满员，无法报名", "error")
            return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 创建报名记录
    new_registration = Registration(
        user_id=user_id,
        activity_id=activity_id,
        register_time=datetime.now(),
    )

    try:
        db.session.add(new_registration)
        db.session.commit()
        flash("报名成功！", "success")
    except Exception as e:
        db.session.rollback()
        flash("报名失败，请稍后重试", "error")

    return redirect(url_for("activity.activity_detail", activity_id=activity_id))
