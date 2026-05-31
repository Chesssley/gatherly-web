import os
from collections import defaultdict

from flask import Blueprint, abort, jsonify, render_template, request, session, redirect, url_for, flash
from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError

from app.models import (
    db,
    Activity,
    ActivityFavorite,
    ActivityReview,
    Registration,
    TrustScoreLog,
    User,
    UserReview,
    get_user_display_name,
)
from app.utils.upload_utils import delete_saved_images, save_image_files, validate_image_files

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


RATING_ELIGIBLE_STATUSES = {"attended", "completed"}
TRUST_SCORE_THRESHOLD = 60
ACTIVITY_IMAGE_MAX_BYTES = 800 * 1024
ACTIVITY_IMAGE_UPLOAD_SUBDIR = os.path.join("images", "activities")
ACTIVITY_CARD_AVATAR_LIMIT = 4

USER_REVIEW_FIELDS = (
    "punctuality_score",
    "friendliness_score",
    "communication_score",
    "reliability_score",
    "respect_score",
    "safety_score",
)

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

def _parse_rating_score(field_name):
    raw_value = request.form.get(field_name)
    if raw_value is None or raw_value == "":
        raise ValueError("missing")

    score = int(raw_value)
    if score < 1 or score > 5:
        raise ValueError("out_of_range")
    return score


def _activity_has_ended(activity):
    return bool(activity and activity.start_time and activity.start_time < datetime.utcnow())


def _is_activity_participant(user_id, activity_id):
    return (
        Registration.query.filter(
            Registration.user_id == user_id,
            Registration.activity_id == activity_id,
            Registration.status.in_(RATING_ELIGIBLE_STATUSES),
        ).first()
        is not None
    )


def _recalculate_user_trust_score(user, changed_by_id, related_review_id):
    score_avg = (
        db.session.query(func.avg(UserReview.average_score))
        .filter(
            UserReview.reviewee_id == user.id,
            UserReview.status == "published",
        )
        .scalar()
    )
    if score_avg is None:
        return

    score_before = int(user.trust_score or 0)
    score_after = max(0, min(100, int(round(float(score_avg) * 20))))
    user.trust_score = score_after
    db.session.add(
        TrustScoreLog(
            user_id=user.id,
            changed_by_id=changed_by_id,
            change_type="user_review",
            delta=score_after - score_before,
            score_before=score_before,
            score_after=score_after,
            reason="Trust score recalculated from received user reviews.",
            related_type="user_review",
            related_id=related_review_id,
        )
    )


def _get_rating_stats(activity_id):
    stats = (
        db.session.query(
            func.count(ActivityReview.id).label("rating_count"),
            func.avg(ActivityReview.organization_score).label("organization_avg"),
            func.avg(ActivityReview.venue_score).label("venue_avg"),
            func.avg(ActivityReview.content_score).label("content_avg"),
            func.avg(ActivityReview.value_score).label("value_avg"),
            func.avg(ActivityReview.experience_score).label("experience_avg"),
            func.avg(ActivityReview.average_score).label("overall_avg"),
        )
        .filter(ActivityReview.activity_id == activity_id)
        .one()
    )

    rating_count = int(stats.rating_count or 0)
    if rating_count == 0:
        return {
            "count": 0,
            "organization_avg": None,
            "venue_avg": None,
            "content_avg": None,
            "value_avg": None,
            "experience_avg": None,
            "overall_avg": None,
        }

    return {
        "count": rating_count,
        "organization_avg": round(float(stats.organization_avg), 1),
        "venue_avg": round(float(stats.venue_avg), 1),
        "content_avg": round(float(stats.content_avg), 1),
        "value_avg": round(float(stats.value_avg), 1),
        "experience_avg": round(float(stats.experience_avg), 1),
        "overall_avg": round(float(stats.overall_avg), 1),
    }


def _split_tags(tags):
    return [tag.strip() for tag in (tags or "").split(",") if tag.strip()]


def _activity_time_filter(start_time):
    if not start_time:
        return "any"

    today = datetime.now().date()
    activity_date = start_time.date()
    if activity_date == today:
        return "today"
    if activity_date == today + timedelta(days=1):
        return "tomorrow"
    if activity_date.year == today.year and activity_date.month == today.month:
        week_end = today + timedelta(days=6 - today.weekday())
        if today <= activity_date <= week_end:
            return "weekend" if activity_date.weekday() >= 5 else "week"
        return "month"
    return "any"


def _activity_heat_score(activity, registration_count=0, favorite_count=0):
    current_people = (activity.initial_participants or 0) + registration_count
    score = current_people * 3 + favorite_count * 2
    if activity.start_time:
        days_until_start = (activity.start_time.date() - datetime.now().date()).days
        if 0 <= days_until_start <= 7:
            score += 6
        elif days_until_start <= 14 and days_until_start >= 0:
            score += 3
    return score


def _get_activity_attendee_previews(activity_ids):
    previews_by_activity = defaultdict(list)
    if not activity_ids:
        return previews_by_activity

    rows = (
        db.session.query(Registration.activity_id, User)
        .join(User, User.id == Registration.user_id)
        .filter(Registration.activity_id.in_(activity_ids))
        .order_by(Registration.activity_id.asc(), Registration.register_time.asc())
        .all()
    )
    for activity_id, user in rows:
        previews = previews_by_activity[activity_id]
        if len(previews) >= ACTIVITY_CARD_AVATAR_LIMIT:
            continue
        display_name = get_user_display_name(user).strip() or user.username
        previews.append(
            {
                "avatar": user.avatar,
                "display_name": display_name,
                "initial": display_name[:1].upper(),
            }
        )
    return previews_by_activity


def _activity_to_summary(activity, registration_count=0, favorite_count=0, attendee_previews=None):
    tags = _split_tags(activity.tags)
    category = tags[0] if tags else DEFAULT_ACTIVITY_TAG
    heat_score = _activity_heat_score(activity, registration_count, favorite_count)
    current_people = (activity.initial_participants or 0) + registration_count
    attendee_previews = attendee_previews or []
    return {
        "id": activity.id,
        "title": activity.title,
        "description": activity.description,
        "detail": activity.detail,
        "city": activity.city,
        "location": activity.location,
        "time": activity.start_time.strftime("%Y-%m-%d %H:%M") if activity.start_time else "时间待定",
        "time_filter": _activity_time_filter(activity.start_time),
        "category": category,
        "tags": tags or [category],
        "image_url": activity.image,
        "organizer": (
            "Gatherly官方活动"
            if activity.organizer and activity.organizer.role == "admin"
            else activity.organizer.nickname or activity.organizer.username
            if activity.organizer
            else "Gatherly 活动发起人"
        ),
        "current_people": current_people,
        "attendee_previews": attendee_previews,
        "attendee_remaining_count": max(0, current_people - len(attendee_previews)),
        "favorite_count": favorite_count,
        "heat_score": heat_score,
        "is_featured": activity.is_featured,
        "is_upcoming": not activity.start_time or activity.start_time >= datetime.now(),
        "fee": activity.fee,
        "status": activity.status,
        "demo": activity.id <= 7,
        "detail_url": url_for("activity.activity_detail", activity_id=activity.id),
    }


@activity_bp.route("/")
def index():
    selected_tag = request.args.get("tag", "").strip()
    interest_tags = OFFICIAL_INTEREST_TAGS
    categories = interest_tags
    visible_tag_count = len(interest_tags)
    db_activities = Activity.query.all()
    reg_counts = dict(
        db.session.query(Registration.activity_id, func.count(Registration.id))
        .group_by(Registration.activity_id)
        .all()
    )
    favorite_counts = dict(
        db.session.query(ActivityFavorite.activity_id, func.count(ActivityFavorite.id))
        .group_by(ActivityFavorite.activity_id)
        .all()
    )
    attendee_previews = _get_activity_attendee_previews([activity.id for activity in db_activities])
    normalized_activities = [
        _activity_to_summary(
            activity,
            reg_counts.get(activity.id, 0),
            favorite_counts.get(activity.id, 0),
            attendee_previews.get(activity.id, []),
        )
        for activity in db_activities
    ]
    normalized_activities.sort(
        key=lambda activity: (
            -activity["heat_score"],
            -activity["current_people"],
            activity["time"],
            activity["id"],
        )
    )
    hot_activity_ids = {
        activity["id"]
        for activity in normalized_activities[:3]
        if activity["heat_score"] > 0
    }
    for activity in normalized_activities:
        activity["is_hot"] = activity["id"] in hot_activity_ids
    featured_activities = [
        activity
        for activity in normalized_activities
        if activity["is_featured"] and activity["is_upcoming"] and activity["status"] == "open"
    ]

    if selected_tag and selected_tag in interest_tags:
        filtered_activities = [
            activity for activity in normalized_activities if activity["category"] == selected_tag
        ]
    else:
        filtered_activities = normalized_activities
        selected_tag = ""

    expand_tags_by_default = (
        bool(selected_tag)
        and interest_tags.index(selected_tag) >= visible_tag_count
    )

    favorite_activity_ids = set()
    favorite_activities = []
    registered_activities = []
    if "user_id" in session:
        user_id = session["user_id"]
        activity_lookup = {activity.id: activity for activity in db_activities}

        registration_rows = (
            Registration.query.filter_by(user_id=user_id)
            .order_by(Registration.register_time.desc())
            .all()
        )
        favorite_rows = (
            ActivityFavorite.query.filter_by(user_id=user_id)
            .order_by(ActivityFavorite.created_at.desc())
            .all()
        )

        favorite_activity_ids = {favorite.activity_id for favorite in favorite_rows}
        registered_activities = [
            _activity_to_summary(
                activity_lookup[row.activity_id],
                reg_counts.get(row.activity_id, 0),
                favorite_counts.get(row.activity_id, 0),
            )
            for row in registration_rows
            if row.activity_id in activity_lookup
        ]
        favorite_activities = [
            _activity_to_summary(
                activity_lookup[row.activity_id],
                reg_counts.get(row.activity_id, 0),
                favorite_counts.get(row.activity_id, 0),
            )
            for row in favorite_rows
            if row.activity_id in activity_lookup
        ]

    return render_template(
        "index.html",
        activities=filtered_activities,
        featured_activities=featured_activities,
        categories=categories,
        expand_tags_by_default=expand_tags_by_default,
        interest_tags=interest_tags,
        selected_tag=selected_tag,
        visible_tag_count=visible_tag_count,
        registered_activities=registered_activities,
        favorite_activity_ids=favorite_activity_ids,
        favorite_activities=favorite_activities,
    )


@activity_bp.route("/my-events")
@login_required
def my_events():
    user_id = session["user_id"]
    active_tab = request.args.get("tab", "joined")
    tab_labels = {
        "created": "我创建的活动",
        "joined": "我报名的活动",
        "saved": "我收藏的活动",
    }
    if active_tab not in tab_labels:
        active_tab = "joined"

    active_status = request.args.get("status", "all")
    status_labels = {
        "all": "全部",
        "upcoming": "即将开始",
        "ended": "已结束",
    }
    if active_status not in status_labels:
        active_status = "all"

    search_query = request.args.get("q", "").strip()

    if active_tab == "created":
        query = Activity.query.filter(Activity.organizer_id == user_id)
    elif active_tab == "saved":
        query = (
            Activity.query.join(
                ActivityFavorite,
                ActivityFavorite.activity_id == Activity.id,
            )
            .filter(ActivityFavorite.user_id == user_id)
        )
    else:
        query = (
            Activity.query.join(
                Registration,
                Registration.activity_id == Activity.id,
            )
            .filter(Registration.user_id == user_id)
            .distinct()
        )

    now = datetime.utcnow()
    ended_filter = or_(
        Activity.status == "closed",
        and_(Activity.start_time.isnot(None), Activity.start_time < now),
    )
    if active_status == "upcoming":
        query = query.filter(
            Activity.status != "closed",
            or_(Activity.start_time.is_(None), Activity.start_time >= now),
        )
        ordering = (Activity.start_time.asc(), Activity.id.desc())
    elif active_status == "ended":
        query = query.filter(ended_filter)
        ordering = (Activity.start_time.desc(), Activity.id.desc())
    else:
        ordering = (Activity.start_time.desc(), Activity.id.desc())

    if search_query:
        query = query.filter(Activity.title.ilike(f"%{search_query}%"))

    db_activities = query.order_by(*ordering).all()
    activity_ids = [activity.id for activity in db_activities]
    reg_counts = {}
    if activity_ids:
        reg_counts = dict(
            db.session.query(Registration.activity_id, func.count(Registration.id))
            .filter(Registration.activity_id.in_(activity_ids))
            .group_by(Registration.activity_id)
            .all()
        )

    activities = [
        _activity_to_summary(activity, reg_counts.get(activity.id, 0))
        for activity in db_activities
    ]
    return render_template(
        "my_events.html",
        active_tab=active_tab,
        active_status=active_status,
        search_query=search_query,
        activities=activities,
        tab_labels=tab_labels,
        status_labels=status_labels,
    )


@activity_bp.route("/activity/<int:activity_id>")
def activity_detail(activity_id):
    db_activity = Activity.query.get_or_404(activity_id)
    registration_rows_count = Registration.query.filter_by(activity_id=activity_id).count()
    registration_count = (db_activity.initial_participants or 0) + registration_rows_count
    activity = _activity_to_summary(db_activity, registration_rows_count)
    if db_activity is None:
        abort(404)
    max_participants = db_activity.max_participants
    preparation = db_activity.preparation
    rating_stats = _get_rating_stats(activity_id)

    user_registered = False
    is_favorited = False
    user_attended = False
    has_rated = False
    can_rate = False
    rating_notice = "登录并报名参加活动后，可在活动结束后评分。"

    if "user_id" not in session:
        rating_notice = "请先登录后再评分。"
    else:
        is_favorited = ActivityFavorite.query.filter_by(
            user_id=session["user_id"], activity_id=activity_id
        ).first() is not None
        registration = Registration.query.filter_by(
            user_id=session["user_id"], activity_id=activity_id
        ).first()
        user_registered = registration is not None
        user_attended = (
            registration is not None
            and registration.status in RATING_ELIGIBLE_STATUSES
        )
        has_rated = ActivityReview.query.filter_by(
            reviewer_id=session["user_id"], activity_id=activity_id
        ).first() is not None

        if not user_registered:
            rating_notice = "只有已报名并参加该活动的用户可以评分。"
        elif not user_attended:
            rating_notice = "只有已报名并参加该活动的用户可以评分。"
        elif has_rated:
            rating_notice = "您已提交过评分，不能重复评分。"
        elif not db_activity or not db_activity.start_time:
            rating_notice = "活动时间未确认，暂不能评分。"
        elif not _activity_has_ended(db_activity):
            rating_notice = "活动尚未结束，暂不能评分。"
        else:
            can_rate = True
            rating_notice = ""

    can_user_review = False
    user_review_notice = "Log in and attend this activity before reviewing other participants."
    user_review_candidates = []

    if "user_id" in session:
        user_id = session["user_id"]
        if not user_attended:
            user_review_notice = "Only actual participants can review other participants."
        elif not _activity_has_ended(db_activity):
            user_review_notice = "Participant reviews open after the activity has ended."
        else:
            reviewed_user_ids = {
                review.reviewee_id
                for review in UserReview.query.filter_by(
                    activity_id=activity_id,
                    reviewer_id=user_id,
                ).all()
            }
            participant_rows = (
                db.session.query(User)
                .join(Registration, Registration.user_id == User.id)
                .filter(
                    Registration.activity_id == activity_id,
                    Registration.status.in_(RATING_ELIGIBLE_STATUSES),
                    User.id != user_id,
                )
                .order_by(User.username.asc())
                .all()
            )
            user_review_candidates = [
                {
                    "user": participant,
                    "has_reviewed": participant.id in reviewed_user_ids,
                }
                for participant in participant_rows
            ]
            can_user_review = any(
                not candidate["has_reviewed"] for candidate in user_review_candidates
            )
            if not user_review_candidates:
                user_review_notice = "No other attended participants are available for review."
            elif not can_user_review:
                user_review_notice = "You have reviewed all available participants for this activity."
            else:
                user_review_notice = ""

    return render_template(
        "activity_detail.html",
        activity=activity,
        registration_count=registration_count,
        max_participants=max_participants,
        preparation=preparation,
        user_registered=user_registered,
        is_favorited=is_favorited,
        has_rated=has_rated,
        can_rate=can_rate,
        rating_notice=rating_notice,
        rating_stats=rating_stats,
        can_user_review=can_user_review,
        user_review_candidates=user_review_candidates,
        user_review_notice=user_review_notice,
    )


@activity_bp.route("/activity/<int:activity_id>/favorite", methods=["POST"])
def toggle_activity_favorite(activity_id):
    if "user_id" not in session:
        return jsonify(
            {
                "error": "login_required",
                "login_url": url_for(
                    "auth.login",
                    next=url_for("activity.activity_detail", activity_id=activity_id),
                ),
            }
        ), 401

    Activity.query.get_or_404(activity_id)

    favorite = ActivityFavorite.query.filter_by(
        user_id=session["user_id"],
        activity_id=activity_id,
    ).first()
    if favorite is not None:
        db.session.delete(favorite)
        is_favorited = False
    else:
        db.session.add(
            ActivityFavorite(
                user_id=session["user_id"],
                activity_id=activity_id,
            )
        )
        is_favorited = True

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        is_favorited = True

    return jsonify({"is_favorited": is_favorited})


@activity_bp.route("/activities/create", methods=["GET", "POST"])
@login_required  # 登录校验
def create_activity():
    current_user = User.query.get(session["user_id"])
    if (
        current_user
        and current_user.role != "admin"
        and current_user.trust_score < TRUST_SCORE_THRESHOLD
    ):
        flash("Your trust score is below 60, so you cannot create activities yet.", "error")
        return redirect(url_for("activity.index"))

    if request.method == "GET":
        return render_template("activity_create.html", interest_tags=OFFICIAL_INTEREST_TAGS)

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    detail = request.form.get("detail", "").strip()
    city = request.form.get("city", "").strip()
    location = request.form.get("location", "").strip()
    preparation = request.form.get("preparation", "").strip()
    tags = [
        tag for tag in request.form.getlist("tags")
        if tag in OFFICIAL_INTEREST_TAGS
    ]
    errors = []

    try:
        start_time = datetime.fromisoformat(request.form.get("start_time", ""))
        if start_time <= datetime.now():
            errors.append("活动时间必须晚于当前时间。")
    except ValueError:
        start_time = None
        errors.append("请选择有效的活动时间。")

    try:
        max_participants = int(request.form.get("max_participants", ""))
        if max_participants < 1:
            raise ValueError
    except ValueError:
        max_participants = None
        errors.append("人数上限必须是大于 0 的整数。")

    try:
        fee = float(request.form.get("fee", ""))
        if fee < 0:
            raise ValueError
    except ValueError:
        fee = None
        errors.append("费用必须是大于等于 0 的数字。")

    if not title:
        errors.append("请填写活动标题。")
    if not description:
        errors.append("请填写活动简介。")
    if not detail:
        errors.append("请填写活动详情。")
    if not city:
        errors.append("请填写城市或地区。")
    if not location:
        errors.append("请填写详细地点。")
    if not tags:
        errors.append("请至少选择一个兴趣标签。")
    if not preparation:
        errors.append("请填写准备事项。")

    validated_images = []
    try:
        validated_images = validate_image_files(
            [request.files.get("image")],
            max_count=1,
            max_bytes=ACTIVITY_IMAGE_MAX_BYTES,
        )
        if not validated_images:
            errors.append("请上传一张活动图片。")
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("activity_create.html", interest_tags=OFFICIAL_INTEREST_TAGS), 400

    saved_paths = []
    try:
        saved_paths = save_image_files(validated_images, ACTIVITY_IMAGE_UPLOAD_SUBDIR)
        activity = Activity(
            title=title,
            description=description,
            detail=detail,
            city=city,
            location=location,
            start_time=start_time,
            max_participants=max_participants,
            initial_participants=0,
            image=f"/static/{saved_paths[0]}",
            fee=fee,
            tags=",".join(tags),
            preparation=preparation,
            organizer_id=current_user.id,
        )
        db.session.add(activity)
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_saved_images(saved_paths)
        flash("活动发布失败，请稍后重试。", "error")
        return render_template("activity_create.html", interest_tags=OFFICIAL_INTEREST_TAGS), 500

    flash("活动发布成功。", "success")
    return redirect(url_for("activity.activity_detail", activity_id=activity.id))

@activity_bp.route("/activity/<int:activity_id>/register", methods=["POST"])
def register_activity(activity_id):
    """活动报名路由"""
    # 检查用户是否登录，未登录则重定向到登录页并带上next参数
    if "user_id" not in session:
        flash("请先登录后再报名活动", "error")
        next_url = url_for("activity.activity_detail", activity_id=activity_id)
        return redirect(url_for("auth.login", next=next_url))

    db_activity = Activity.query.get_or_404(activity_id)

    user_id = session["user_id"]

    # ===== US-05-03：重复报名检查 =====
    existing = Registration.query.filter_by(user_id=user_id, activity_id=activity_id).first()
    if existing:
        flash("您已报名该活动，无需重复报名", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 检查活动是否已过期
    if db_activity.start_time and db_activity.start_time < datetime.utcnow():
        flash("该活动已过期，无法报名", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 检查是否已满员
    if db_activity.max_participants is not None:
        current_count = (
            (db_activity.initial_participants or 0)
            + Registration.query.filter_by(activity_id=activity_id).count()
        )
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

    Activity.query.get_or_404(activity_id)

    user_id = session["user_id"]

    db_activity = Activity.query.get(activity_id)
    if not db_activity or not db_activity.start_time:
        flash("活动时间未确认，暂不能评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    if not _activity_has_ended(db_activity):
        flash("活动尚未结束，暂不能评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    registered = Registration.query.filter_by(
        user_id=user_id, activity_id=activity_id
    ).first()
    if not registered or registered.status not in RATING_ELIGIBLE_STATUSES:
        flash("只有已报名并参加该活动的用户可以评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    existing = ActivityReview.query.filter_by(
        reviewer_id=user_id, activity_id=activity_id
    ).first()
    if existing:
        flash("您已提交过评分，不能重复评分", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    try:
        org_score = _parse_rating_score("organization_score")
        venue_score = _parse_rating_score("venue_score")
        content_score = _parse_rating_score("content_score")
        value_score = _parse_rating_score("value_score")
        exp_score = _parse_rating_score("experience_score")
    except (TypeError, ValueError):
        flash("每个评分必须是 1 到 5 的整数", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    avg_score = round(
        (org_score + venue_score + content_score + value_score + exp_score) / 5,
        1,
    )

    comment = request.form.get("comment", "").strip()

    rating = ActivityReview(
        reviewer_id=user_id,
        activity_id=activity_id,
        organization_score=org_score,
        venue_score=venue_score,
        content_score=content_score,
        value_score=value_score,
        experience_score=exp_score,
        average_score=avg_score,
        comment=comment or None,
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


@activity_bp.route("/activity/<int:activity_id>/user-reviews", methods=["POST"])
def submit_user_review(activity_id):
    if "user_id" not in session:
        flash("Please log in before reviewing participants.", "error")
        return redirect(url_for("auth.login", next=url_for("activity.activity_detail", activity_id=activity_id)))

    Activity.query.get_or_404(activity_id)

    db_activity = Activity.query.get(activity_id)
    if not _activity_has_ended(db_activity):
        flash("Participant reviews are only available after the activity ends.", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    reviewer_id = session["user_id"]
    try:
        reviewee_id = int(request.form.get("reviewee_id", ""))
    except (TypeError, ValueError):
        flash("Please choose a valid participant to review.", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    if reviewer_id == reviewee_id:
        flash("You cannot review yourself.", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    if not _is_activity_participant(reviewer_id, activity_id):
        flash("Only actual participants can submit participant reviews.", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    reviewee = User.query.get(reviewee_id)
    if not reviewee or not _is_activity_participant(reviewee_id, activity_id):
        flash("The reviewed user must be an actual participant in this activity.", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    existing = UserReview.query.filter_by(
        activity_id=activity_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
    ).first()
    if existing:
        flash("You have already reviewed this participant for this activity.", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    try:
        scores = {field: _parse_rating_score(field) for field in USER_REVIEW_FIELDS}
    except (TypeError, ValueError):
        flash("Each participant review score must be an integer from 1 to 5.", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    average_score = round(sum(scores.values()) / len(scores), 1)
    comment = request.form.get("comment", "").strip()

    user_review = UserReview(
        activity_id=activity_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        average_score=average_score,
        comment=comment or None,
        **scores,
    )

    try:
        db.session.add(user_review)
        db.session.flush()
        _recalculate_user_trust_score(reviewee, reviewer_id, user_review.id)
        db.session.commit()
        flash("Participant review submitted.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("You have already reviewed this participant for this activity.", "error")
    except Exception:
        db.session.rollback()
        flash("Participant review submission failed. Please try again later.", "error")

    return redirect(url_for("activity.activity_detail", activity_id=activity_id))
