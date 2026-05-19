from flask import Blueprint, abort, render_template

from app.models import activities

activity_bp = Blueprint("activity", __name__)


@activity_bp.route("/")
def index():
    return render_template("index.html", activities=activities)


@activity_bp.route("/activities/<int:activity_id>")
def activity_detail(activity_id):
    activity = next((item for item in activities if item["id"] == activity_id), None)
    if activity is None:
        abort(404)
    return render_template("activity_detail.html", activity=activity)


@activity_bp.route("/activities/create")
def create_activity():
    return render_template("create_activity.html")
