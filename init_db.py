# -*- coding: utf-8 -*-
"""数据库初始化脚本"""

from app import create_app
from app.models import db

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ 数据库初始化完成！")
    print("📁 数据库文件: gatherly.db")
