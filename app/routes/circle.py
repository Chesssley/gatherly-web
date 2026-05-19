from flask import Blueprint, render_template

from app.models import circles

circle_bp = Blueprint("circle", __name__)


@circle_bp.route("/circles")
def circle_list():
    return render_template("circle.html", circles=circles)
