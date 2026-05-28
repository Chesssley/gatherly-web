from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nickname = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255))
    interests = db.Column(db.Text)
    role = db.Column(db.String(20), default="user", nullable=False)
    trust_score = db.Column(db.Integer, default=100, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    activities = db.relationship("Activity", back_populates="organizer")
    registrations = db.relationship("Registration", back_populates="user")
    posts = db.relationship("Post", back_populates="user")
    reviews = db.relationship("Review", back_populates="user")

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(255))
    start_time = db.Column(db.DateTime)
    max_participants = db.Column(db.Integer)
    image = db.Column(db.String(255))
    fee = db.Column(db.Float, default=0, nullable=False)
    status = db.Column(db.String(20), default="open", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    preparation = db.Column(db.Text)  # 活动准备事项

    organizer = db.relationship("User", back_populates="activities")
    registrations = db.relationship("Registration", back_populates="activity")
    reviews = db.relationship("Review", back_populates="activity")


class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    status = db.Column(db.String(20), default="registered", nullable=False)
    register_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="registrations")
    activity = db.relationship("Activity", back_populates="registrations")


class Circle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    tag = db.Column(db.String(50))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    posts = db.relationship("Post", back_populates="circle")


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey("circle.id"), nullable=False)

    user = db.relationship("User", back_populates="posts")
    circle = db.relationship("Circle", back_populates="posts")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    activity = db.relationship("Activity", back_populates="reviews")
    user = db.relationship("User", back_populates="reviews")


# Temporary data kept only so the existing page routes can run before database
# query logic is implemented in later tasks.
activities = [
    {
        "id": 1,
        "title": "示例活动标题",
        "category": "示例标签",
        "time": "待补充",
        "location": "待补充",
        "capacity": "待补充",
        "description": "待补充活动简介",
        "detail": "待补充活动详情",
    }
]

circles = [
    {
        "id": 1,
        "name": "示例圈子名称",
        "tag": "示例标签",
        "summary": "待补充圈子简介",
        "members": 0,
    }
]
