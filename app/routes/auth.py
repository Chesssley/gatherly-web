from flask import Blueprint, render_template

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    """
    登录页路由。
    TODO: TASK-004 登录注册负责人补充登录表单和验证逻辑。
    """
    return render_template("login.html")


@auth_bp.route("/register")
def register():
    """
    注册页路由。
    TODO: TASK-004 登录注册负责人补充注册表单和验证逻辑。
    """
    return render_template("register.html")