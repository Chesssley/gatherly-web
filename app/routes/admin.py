from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.models import User

admin_bp = Blueprint("admin", __name__)


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("auth.login", next=request.url))
        if user.role != "admin":
            flash("您没有权限访问后台管理系统。", "error")
            return redirect(url_for("activity.index"))
        return view(*args, **kwargs)

    return wrapped_view


@admin_bp.app_context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


@admin_bp.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")
