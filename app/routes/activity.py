from flask import Blueprint, abort, render_template, request

from app.models import Activity, Registration, activities

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/")
def index():
    selected_tag = request.args.get("tag", "").strip()
    categories = sorted({activity["category"] for activity in activities})

    if selected_tag and selected_tag in categories:
        filtered_activities = [
            activity for activity in activities if activity["category"] == selected_tag
        ]
    else:
        filtered_activities = activities
        selected_tag = ""

    return render_template(
        "index.html",
        activities=filtered_activities,
        categories=categories,
        selected_tag=selected_tag,
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
