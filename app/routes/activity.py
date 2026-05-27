from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from app.models import Activity, Registration, activities, db

activity_bp = Blueprint("activity", __name__)


def login_required(f):
    """要求登录态的装饰器，未登录时重定向到登录页。"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash("请先登录后再操作", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


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

    # 从数据库合并真实报名人数到硬编码活动数据
    try:
        activity_ids = [a["id"] for a in filtered_activities]
        registrations = (
            db.session.query(
                Registration.activity_id,
                db.func.count(Registration.id).label("cnt"),
            )
            .filter(Registration.activity_id.in_(activity_ids))
            .group_by(Registration.activity_id)
            .all()
        )
        reg_map = {row.activity_id: row.cnt for row in registrations}

        db_activities = Activity.query.filter(Activity.id.in_(activity_ids)).all()
        capacity_map = {a.id: a.max_participants for a in db_activities}

        for activity in filtered_activities:
            aid = activity["id"]
            cnt = reg_map.get(aid, 0)
            activity["current_people"] = cnt
            cap = capacity_map.get(aid)
            activity["max_people"] = str(cap) if cap is not None else "不限"
    except Exception:
        pass

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

        user_id = session.get("user_id")
        user_registered = False
        if user_id:
            user_registered = (
                Registration.query.filter_by(
                    user_id=user_id, activity_id=activity_id
                ).first()
                is not None
            )
    except Exception:
        registration_count = 0
        max_participants = None
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
    return render_template("create_activity.html")


@activity_bp.route("/activity/<int:activity_id>/register", methods=["POST"])
@login_required
def register_activity(activity_id):
    """活动报名路由：登录用户报名参加指定活动。"""
    user_id = session.get("user_id")

    activity = next((a for a in activities if a.get("id") == activity_id), None)
    if activity is None:
        if request.is_json:
            return jsonify({"success": False, "message": "活动不存在"}), 404
        abort(404)

    db_activity = Activity.query.get(activity_id)
    if db_activity and db_activity.start_time and db_activity.start_time < datetime.utcnow():
        flash("报名失败，活动已过期", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    if db_activity and db_activity.max_participants is not None:
        current_count = Registration.query.filter_by(activity_id=activity_id).count()
        if current_count >= db_activity.max_participants:
            msg = "该活动已满员"
            if request.is_json:
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, "error")
            return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    existing = Registration.query.filter_by(
        user_id=user_id, activity_id=activity_id
    ).first()
    if existing:
        msg = "您已报名该活动"
        if request.is_json:
            return jsonify({"success": False, "message": msg}), 400
        flash(msg, "info")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    try:
        registration = Registration(user_id=user_id, activity_id=activity_id)
        db.session.add(registration)
        db.session.commit()
        msg = "报名成功！"
        if request.is_json:
            return jsonify({"success": True, "message": msg})
        flash(msg, "success")
    except Exception:
        db.session.rollback()
        msg = "报名失败，请稍后重试"
        if request.is_json:
            return jsonify({"success": False, "message": msg}), 500
        flash(msg, "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    return redirect(url_for("activity.activity_detail", activity_id=activity_id))
