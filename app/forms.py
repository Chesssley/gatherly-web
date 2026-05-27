# -*- coding: utf-8 -*-
"""Gatherly 表单定义"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Email, ValidationError
from app.models import User


class RegistrationForm(FlaskForm):
    """用户注册表单（US-02-01）"""

    username = StringField(
        "用户名",
        validators=[
            DataRequired(message="用户名不能为空"),
            Length(min=3, max=80, message="用户名长度需在 3-80 个字符之间"),
        ],
    )

    email = StringField(
        "邮箱",
        validators=[
            DataRequired(message="邮箱不能为空"),
            Email(message="请输入有效的邮箱地址"),
        ],
    )

    password = PasswordField(
        "密码",
        validators=[
            DataRequired(message="密码不能为空"),
            Length(min=6, message="密码长度不能少于 6 个字符"),
        ],
    )

    confirm_password = PasswordField(
        "确认密码",
        validators=[
            DataRequired(message="请再次输入密码"),
            EqualTo("password", message="两次输入的密码不一致"),
        ],
    )

    submit = SubmitField("注册")

    def validate_username(self, field):
        user = User.query.filter_by(username=field.data).first()
        if user:
            raise ValidationError("该用户名已被注册，请选择其他用户名")

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if user:
            raise ValidationError("该邮箱已被注册，请使用其他邮箱或直接登录")
