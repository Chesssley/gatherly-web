from flask import Blueprint, abort, render_template, request

from app.models import Activity, Registration, activities

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

    registration_count = Registration.query.filter_by(activity_id=activity_id).count()
    db_activity = Activity.query.get(activity_id)
    max_participants = db_activity.max_participants if db_activity else None
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
