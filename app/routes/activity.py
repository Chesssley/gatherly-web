from flask import Blueprint, abort, render_template, request, session, redirect, url_for, flash
from functools import wraps
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models import db, Activity, Registration, Rating, activities

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


RATING_ELIGIBLE_STATUSES = {"registered", "attended", "completed"}


def _parse_rating_score(field_name):
    raw_value = request.form.get(field_name)
    if raw_value is None or raw_value == "":
        raise ValueError("missing")

    score = int(raw_value)
    if score < 1 or score > 5:
        raise ValueError("out_of_range")
    return score


def _get_rating_stats(activity_id):
    stats = (
        db.session.query(
            func.count(Rating.id).label("rating_count"),
            func.avg(Rating.organization_score).label("organization_avg"),
            func.avg(Rating.venue_score).label("venue_avg"),
            func.avg(Rating.experience_score).label("experience_avg"),
            func.avg(Rating.average_score).label("overall_avg"),
        )
        .filter(Rating.activity_id == activity_id)
        .one()
    )

    rating_count = int(stats.rating_count or 0)
    if rating_count == 0:
        return {
            "count": 0,
            "organization_avg": None,
            "venue_avg": None,
            "experience_avg": None,
            "overall_avg": None,
        }

    return {
        "count": rating_count,
        "organization_avg": round(float(stats.organization_avg), 1),
        "venue_avg": round(float(stats.venue_avg), 1),
        "experience_avg": round(float(stats.experience_avg), 1),
        "overall_avg": round(float(stats.overall_avg), 1),
    }


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
    reg_counts = dict(
        db.session.query(Registration.activity_id, func.count(Registration.id))
        .group_by(Registration.activity_id)
        .all()
    )

    # 查询数据库中已发布的活动
    db_activities = Activity.query.order_by(Activity.created_at.desc()).all()
    db_acts = []
    for act in db_activities:
        tag_list = [t.strip() for t in act.tags.split(",") if t.strip()] if act.tags else []
        time_str = act.start_time.strftime("%m月%d日 %H:%M") if act.start_time else "待定"
        db_acts.append({
            "id": act.id,
            "title": act.title,
            "category": tag_list[0] if tag_list else "",
            "tags": tag_list,
            "time": time_str,
            "location": act.location or "待定",
            "max_people": act.max_participants or "不限",
            "current_people": reg_counts.get(act.id, 0),
            "image_url": act.image or "",
            "description": act.description or "",
        })

    # 合并：数据库活动在前，硬编码兜底在后
    all_activities = db_acts + activities

    if selected_tag and selected_tag in interest_tags:
        filtered_activities = [
            a for a in all_activities
            if selected_tag in (a.get("tags") or []) or a.get("category") == selected_tag
        ]
    else:
        filtered_activities = all_activities
        selected_tag = ""

    expand_tags_by_default = (
        bool(selected_tag)
        and interest_tags.index(selected_tag) >= visible_tag_count
    )

    # 补齐硬编码活动的报名人数
    for act in filtered_activities:
        if "current_people" not in act:
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
    db_activity = Activity.query.get(activity_id)

    # 硬编码列表中未找到，但有数据库记录，则从 DB 构建 activity dict
    if activity is None and db_activity is not None:
        tag_list = [t.strip() for t in db_activity.tags.split(",") if t.strip()] if db_activity.tags else []
        time_str = db_activity.start_time.strftime("%m月%d日 %H:%M") if db_activity.start_time else "待定"
        activity = {
            "id": db_activity.id,
            "title": db_activity.title,
            "category": tag_list[0] if tag_list else "",
            "tags": tag_list,
            "time": time_str,
            "location": db_activity.location or "待定",
            "description": db_activity.description or "",
            "detail": db_activity.description or "",
            "capacity": str(db_activity.max_participants) if db_activity.max_participants else "不限",
            "max_people": db_activity.max_participants or "不限",
            "current_people": 0,
            "image_url": db_activity.image or "",
        }

    if activity is None:
        abort(404)

registration_count = Registration.query.filter_by(activity_id=activity_id).count()
    db_activity = Activity.query.get(activity_id)
    max_participants = db_activity.max_participants if db_activity else None
    preparation = db_activity.preparation if db_activity else None
    rating_stats = _get_rating_stats(activity_id)

    user_registered = False
    has_rated = False
    can_rate = False
    rating_notice = "登录并报名参加活动后，可在活动结束后评分。"

    if "user_id" not in session:
        rating_notice = "请先登录后再评分。"
    else:
        registration = Registration.query.filter_by(
            user_id=session["user_id"], activity_id=activity_id
        ).first()
        user_registered = (
            registration is not None
            and registration.status in RATING_ELIGIBLE_STATUSES
        )
        has_rated = Rating.query.filter_by(
            user_id=session["user_id"], activity_id=activity_id
        ).first() is not None

        if not user_registered:
            rating_notice = "只有已报名并参加该活动的用户可以评分。"
        elif has_rated:
            rating_notice = "您已提交过评分，不能重复评分。"
        elif not db_activity or not db_activity.start_time:
            rating_notice = "活动时间未确认，暂不能评分。"
        elif db_activity.start_time >= datetime.utcnow():
            rating_notice = "活动尚未结束，暂不能评分。"
        else:
            can_rate = True
            rating_notice = ""

    return render_template(
        "activity_detail.html",
        activity=activity,
        registration_count=registration_count,
        max_participants=max_participants,
        preparation=preparation,
        user_registered=user_registered,
        has_rated=has_rated,
        can_rate=can_rate,
        rating_notice=rating_notice,
        rating_stats=rating_stats,
    )


@activity_bp.route("/activities/create", methods=["GET", "POST"])
@login_required
def create_activity():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        start_time_str = request.form.get("start_time", "").strip()
        location = request.form.get("location", "").strip()
        max_participants_str = request.form.get("max_participants", "").strip()
        fee_str = request.form.get("fee", "").strip()
        tag_list = request.form.getlist("tags[]")
        preparation = request.form.get("preparation", "").strip()

        errors = []
        if not title:
            errors.append("请填写活动标题")
        if not description:
            errors.append("请填写活动介绍")
        if not start_time_str:
            errors.append("请选择活动时间")
        if not location:
            errors.append("请填写活动地点")

        if errors:
            for err in errors:
                flash(err, "error")
            return redirect(url_for("activity.create_activity"))

        try:
            start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("活动时间格式不正确", "error")
            return redirect(url_for("activity.create_activity"))

        max_participants = None
        if max_participants_str:
            try:
                max_participants = int(max_participants_str)
                if max_participants < 1:
                    max_participants = None
            except ValueError:
                pass

        fee = 0.0
        if fee_str:
            try:
                fee = float(fee_str)
            except ValueError:
                pass

        tags_str = ",".join(tag_list) if tag_list else None

        activity = Activity(
            title=title,
            description=description,
            start_time=start_time,
            location=location,
            max_participants=max_participants,
            fee=fee,
            preparation=preparation or None,
            organizer_id=session["user_id"],
            tags=tags_str,
        )

        try:
            db.session.add(activity)
            db.session.commit()
            flash("活动发布成功！", "success")
        except Exception:
            db.session.rollback()
            flash("发布失败，请稍后重试", "error")
            return redirect(url_for("activity.create_activity"))

        return redirect(url_for("activity.index"))

    return render_template("activity_create.html")

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


@activity_bp.route("/activity/<int:activity_id>/rate", methods=["POST"])
def submit_rating(activity_id):
    """活动多维度评分提交路由"""
    if "user_id" not in session:
        flash("请先登录后再评分", "error")
        return redirect(url_for("auth.login", next=url_for("activity.activity_detail", activity_id=activity_id)))

    activity = next((a for a in activities if a.get("id") == activity_id), None)
    if activity is None:
        abort(404)

    user_id = session["user_id"]

    db_activity = Activity.query.get(activity_id)
    if not db_activity or not db_activity.start_time:
        flash("活动时间未确认，暂不能评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    if db_activity.start_time >= datetime.utcnow():
        flash("活动尚未结束，暂不能评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    registered = Registration.query.filter_by(
        user_id=user_id, activity_id=activity_id
    ).first()
    if not registered or registered.status not in RATING_ELIGIBLE_STATUSES:
        flash("只有已报名并参加该活动的用户可以评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    existing = Rating.query.filter_by(user_id=user_id, activity_id=activity_id).first()
    if existing:
        flash("您已提交过评分，不能重复评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    try:
        org_score = _parse_rating_score("organization_score")
        venue_score = _parse_rating_score("venue_score")
        exp_score = _parse_rating_score("experience_score")
    except (TypeError, ValueError):
        flash("每个评分必须是 1 到 5 的整数", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    avg_score = round((org_score + venue_score + exp_score) / 3, 1)

    rating = Rating(
        user_id=user_id,
        activity_id=activity_id,
        organization_score=org_score,
        venue_score=venue_score,
        experience_score=exp_score,
        average_score=avg_score,
    )

    try:
        db.session.add(rating)
        db.session.commit()
        flash("评分提交成功，感谢您的反馈", "success")
    except IntegrityError:
        db.session.rollback()
        flash("您已提交过评分，不能重复评分", "error")
    except Exception:
        db.session.rollback()
        flash("评分提交失败，请稍后重试", "error")

    return redirect(url_for("activity.activity_detail", activity_id=activity_id))
