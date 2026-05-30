# -*- coding: utf-8 -*-
"""认证相关路由（登录 / 注册 / 登出）"""

from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, db, ensure_user_account_schema
from app.forms import RegistrationForm

auth_bp = Blueprint("auth", __name__)


@auth_bp.before_app_request
def ensure_account_schema():
    ensure_user_account_schema()


def _get_session_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    登录页路由。
    GET：显示登录表单
    POST：验证登录表单 → 写入 session → 重定向首页
    支持 next 参数：登录成功后跳转到 next 指定的页面
    """
    next_page = request.args.get("next") or request.form.get("next", "")

    if request.method == "GET" and next_page:
        flash("请先登录后再报名活动", "info")

    if request.method == "POST":
        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not identifier or not password:
            flash("账号或邮箱和密码不能为空", "error")
            return render_template("login.html")

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user:
            flash("账号、邮箱或密码错误", "error")
            return render_template("login.html")

        # 验证密码
        if user.status == "deleted":
            flash("该账号已注销", "error")
            return render_template("login.html")

        if not check_password_hash(user.password, password):
            flash("账号、邮箱或密码错误", "error")
            return render_template("login.html")

        if user.status == "banned":
            flash("该账号已被封禁", "error")
            return render_template("login.html")

        # 登录成功，写入 session
        session.clear()
        session["user_id"] = user.id
        session["nickname"] = user.nickname or user.username
        flash(f"欢迎回来，{session['nickname']}！", "success")

        if next_page:
            return redirect(next_page)
        return redirect(url_for("activity.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """退出登录，清除 session 并重定向到首页"""
    session.clear()
    flash("您已退出登录", "info")
    return redirect(url_for("activity.index"))


@auth_bp.route("/account/settings")
def account_settings():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))
    if user.status == "deleted":
        session.clear()
        flash("该账号已注销", "error")
        return redirect(url_for("activity.index"))
    return render_template("account_settings.html", user=user)


@auth_bp.route("/merchant-verify", methods=["GET", "POST"])
def merchant_verify():
    """商家认证申请页（US-10-01）"""
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))

    if user.status == "deleted":
        session.clear()
        flash("该账号已注销", "error")
        return redirect(url_for("activity.index"))

    if request.method == "POST":
        is_merchant = request.form.get("is_merchant") == "on"
        merchant_name = request.form.get("merchant_name", "").strip()
        merchant_description = request.form.get("merchant_description", "").strip()
        merchant_license = request.form.get("merchant_license", "").strip()

        errors = []
        if not is_merchant:
            errors.append('请勾选「我是商家」')
        if not merchant_name:
            errors.append("请填写商家名称")
        if not merchant_description:
            errors.append("请填写认证说明")
        if not merchant_license:
            errors.append("请上传营业执照或填写执照文件路径")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("merchant_verify.html")

        user.is_merchant = True
        user.merchant_name = merchant_name
        user.merchant_description = merchant_description
        user.merchant_license = merchant_license
        user.merchant_status = "pending"

        try:
            db.session.commit()
            flash("认证申请已提交，等待管理员审核", "success")
        except Exception:
            db.session.rollback()
            flash("提交失败，请稍后重试", "error")

        return redirect(url_for("auth.merchant_verify"))

    return render_template("merchant_verify.html")


@auth_bp.route("/account/delete", methods=["POST"])
def delete_account():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("auth.account_settings")))
    if user.status == "deleted":
        session.clear()
        flash("该账号已注销", "error")
        return redirect(url_for("activity.index"))

    current_password = request.form.get("current_password", "")
    confirm_text = request.form.get("confirm_text", "").strip()
    if not check_password_hash(user.password, current_password):
        flash("当前密码错误", "error")
        return redirect(url_for("auth.account_settings"))
    if confirm_text != "注销账户":
        flash("确认文字不正确", "error")
        return redirect(url_for("auth.account_settings"))

    old_email = user.email
    user.status = "deleted"
    user.deleted_at = datetime.utcnow()
    user.username = f"deleted_user_{user.id}"
    user.email = f"deleted_{user.id}_{old_email}"
    user.nickname = "已注销用户"
    user.avatar = None
    db.session.commit()

    session.clear()
    flash("账号已注销", "success")
    return redirect(url_for("activity.index"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    注册页路由（US-02-01）。
    GET：显示注册表单
    POST：验证表单 → 密码加密 → 写入数据库 → 重定向到登录页
    """
    form = RegistrationForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        nickname = request.form.get("nickname", "").strip() or username
        email = form.email.data.strip()

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("该用户名已被注册，请选择其他用户名", "error")
            return render_template("register.html", form=form)

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash("该邮箱已被注册，请使用其他邮箱或直接登录", "error")
            return render_template("register.html", form=form)

        hashed_password = generate_password_hash(form.password.data)

        new_user = User(
            username=username,
            nickname=nickname,
            email=email,
            password=hashed_password,
            role="user",
            trust_score=100,
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("注册成功！现在可以登录了。", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            if "UNIQUE constraint failed" in str(e):
                if "username" in str(e):
                    flash("该用户名已被注册，请选择其他用户名", "error")
                elif "email" in str(e):
                    flash("该邮箱已被注册，请使用其他邮箱", "error")
            else:
                flash("注册失败，请稍后重试。", "error")

    return render_template("register.html", form=form)
