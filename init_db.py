# -*- coding: utf-8 -*-
"""数据库初始化脚本"""

import os

from werkzeug.security import generate_password_hash

from app import create_app
from app.models import Activity, User, db, ensure_activity_schema, ensure_user_account_schema
from seed_data import DEMO_ACTIVITIES

app = create_app()

with app.app_context():
    db.create_all()
    ensure_user_account_schema()
    ensure_activity_schema()

    demo_organizer = User.query.filter_by(username="gatherly_demo").first()
    if demo_organizer is None:
        demo_organizer = User(
            username="gatherly_demo",
            nickname="Gatherly 活动发起人",
            email="gatherly_demo@example.invalid",
            password=generate_password_hash(os.urandom(32).hex()),
        )
        db.session.add(demo_organizer)
        db.session.flush()

    for activity_data in DEMO_ACTIVITIES:
        activity = db.session.get(Activity, activity_data["id"])
        if activity is None:
            activity = Activity(id=activity_data["id"], organizer_id=demo_organizer.id)
            db.session.add(activity)
        for field, value in activity_data.items():
            if field != "id":
                setattr(activity, field, value)
    db.session.commit()

    print("数据库初始化完成！")
    print("数据库文件: gatherly.db")

    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if admin_username and admin_email and admin_password:
        admin = User.query.filter(
            (User.username == admin_username) | (User.email == admin_email)
        ).first()
        hashed_password = generate_password_hash(admin_password)

        if admin:
            admin.role = "admin"
            admin.password = hashed_password
            db.session.commit()
            print(f"已升级管理员账号: {admin.username}")
        else:
            admin = User(
                username=admin_username,
                nickname=admin_username,
                email=admin_email,
                password=hashed_password,
                role="admin",
                trust_score=100,
            )
            db.session.add(admin)
            db.session.commit()
            print(f"已创建管理员账号: {admin.username}")
    else:
        print("未创建管理员账号：请同时设置 ADMIN_USERNAME、ADMIN_EMAIL 和 ADMIN_PASSWORD。")
