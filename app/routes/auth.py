# -*- coding: utf-8 -*-
"""认证相关路由（登录 / 注册 / 登出）"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db, User
from app.forms import RegistrationForm

auth_bp = Blueprint("auth", __name__)


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
        if not check_password_hash(user.password, password):
            flash("账号、邮箱或密码错误", "error")
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