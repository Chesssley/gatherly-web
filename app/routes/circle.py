from flask import Blueprint, render_template

from app.models import circles

circle_bp = Blueprint("circle", __name__)


@circle_bp.route("/circles")
def circles():
    """
    同好圈页面路由。
    TODO: TASK-005 同好圈负责人完善圈子列表、圈子详情和帖子功能。
    """
    return render_template("circle.html", circles=circles)