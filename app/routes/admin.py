from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import User, db

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


@admin_bp.route("/admin/account", methods=["GET", "POST"])
@admin_required
def admin_account():
    user = get_current_user()

    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not nickname:
            flash("昵称不能为空。", "error")
        elif not username:
            flash("用户名不能为空。", "error")
        elif not email:
            flash("邮箱不能为空。", "error")
        elif not current_password or not check_password_hash(user.password, current_password):
            flash("当前密码错误，无法保存管理员账号信息。", "error")
        elif User.query.filter(User.username == username, User.id != user.id).first():
            flash("该用户名已被其他用户占用，请更换后重试。", "error")
        elif User.query.filter(User.email == email, User.id != user.id).first():
            flash("该邮箱已被其他用户占用，请更换后重试。", "error")
        elif confirm_password and not new_password:
            flash("请输入新密码。", "error")
        elif new_password and new_password != confirm_password:
            flash("新密码和确认新密码不一致，无法保存。", "error")
        elif new_password and len(new_password) < 6:
            flash("新密码至少需要 6 个字符。", "error")
        else:
            user.nickname = nickname
            user.username = username
            user.email = email
            if new_password:
                user.password = generate_password_hash(new_password)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("用户名或邮箱已被其他用户占用，请更换后重试。", "error")
            else:
                session["nickname"] = user.nickname or user.username
                flash("管理员账号信息已更新", "success")
                return redirect(url_for("admin.admin_account"))

    return render_template("admin_account.html", user=user)
