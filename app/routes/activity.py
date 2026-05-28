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

OFFICIAL_INTEREST_TAGS = [
    "影像摄影",
    "运动户外",
    "咖啡茶饮",
    "阅读出版",
    "手作艺术",
    "音乐演出",
    "观影戏剧",
    "城市探索",
    "游戏桌游",
    "科技数码",
    "美食烘焙",
    "公益志愿",
]

DEFAULT_ACTIVITY_TAG = "城市探索"

ACTIVITY_TAG_OVERRIDES = {
    1: DEFAULT_ACTIVITY_TAG,
}


def _official_activity_tag(activity):
    tag = ACTIVITY_TAG_OVERRIDES.get(activity.get("id"), activity.get("category", ""))
    if tag in OFFICIAL_INTEREST_TAGS:
        return tag
    return DEFAULT_ACTIVITY_TAG


def _with_official_activity_tags(activity):
    normalized = dict(activity)
    official_tag = _official_activity_tag(activity)
    normalized["category"] = official_tag
    normalized["tags"] = [official_tag]
    return normalized


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
    interest_tags = OFFICIAL_INTEREST_TAGS
    visible_tag_count = len(interest_tags)

    # 硬编码示例活动（兼容过渡期）
    normalized_activities = [_with_official_activity_tags(activity) for activity in activities]

    # 数据库活动（最新在前）
    db_activities = Activity.query.order_by(Activity.id.desc()).all()
    db_activity_dicts = []
    for act in db_activities:
        db_activity_dicts.append({
            "id": act.id,
            "title": act.title,
            "category": DEFAULT_ACTIVITY_TAG,
            "tags": [DEFAULT_ACTIVITY_TAG],
            "time": act.start_time.strftime("%Y-%m-%d %H:%M") if act.start_time else "待定",
            "location": act.location or "待补充",
            "max_people": act.max_participants or 0,
            "image_url": act.image or "",
            "description": act.description or "",
        })

    # 合并：数据库活动在前，硬编码示例在后
    all_activities = db_activity_dicts + normalized_activities

    if selected_tag and selected_tag in interest_tags:
        filtered_activities = [
            a for a in all_activities if a.get("category") == selected_tag
        ]
    else:
        filtered_activities = all_activities
        selected_tag = ""

    expand_tags_by_default = (
        bool(selected_tag)
        and interest_tags.index(selected_tag) >= visible_tag_count
    )

    # 合并真实报名人数
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
        categories=interest_tags,
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
    activity = _with_official_activity_tags(activity)

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
        preparation = request.form.get("preparation", "").strip()
        tags = request.form.getlist("tags[]")

        # 基本校验
        errors = []
        if not title:
            errors.append("活动标题不能为空")
        if not description:
            errors.append("活动介绍不能为空")
        if not start_time_str:
            errors.append("活动时间不能为空")
        if not location:
            errors.append("活动地点不能为空")
        if not max_participants_str:
            errors.append("人数上限不能为空")
        if not fee_str:
            errors.append("活动费用不能为空")
        if not preparation:
            errors.append("准备事项不能为空")

        start_time = None
        if start_time_str:
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                errors.append("活动时间格式不正确")

        max_participants = None
        if max_participants_str:
            try:
                max_participants = int(max_participants_str)
                if max_participants < 1:
                    errors.append("人数上限必须大于0")
            except ValueError:
                errors.append("人数上限必须是数字")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("activity_create.html")

        new_activity = Activity(
            title=title,
            description=description,
            start_time=start_time,
            location=location,
            max_participants=max_participants,
            fee=0.0,
            preparation=preparation,
            organizer_id=session["user_id"],
        )

        try:
            db.session.add(new_activity)
            db.session.commit()
            flash("活动发布成功！", "success")
            return redirect(url_for("activity.index"))
        except Exception:
            db.session.rollback()
            flash("发布失败，请稍后重试", "error")
            return render_template("activity_create.html")

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
