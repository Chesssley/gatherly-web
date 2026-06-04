from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.models import Feedback, User, create_notification, db


pages_bp = Blueprint("pages", __name__)

FEEDBACK_CATEGORIES = (
    "功能问题",
    "页面显示问题",
    "活动/报名问题",
    "同好圈/帖子问题",
    "私信/通知问题",
    "其他建议",
)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("请先登录后再提交或查看反馈。", "error")
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@pages_bp.route("/community-guidelines")
def community_guidelines():
    return render_template("pages/community_guidelines.html")


@pages_bp.route("/safety-tips")
def safety_tips():
    return render_template("pages/safety_tips.html")


@pages_bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    user = _current_user()
    if user is None:
        if request.method == "POST":
            flash("请先登录后再提交反馈。", "error")
            return redirect(url_for("auth.login", next=request.url))
        return render_template(
            "pages/feedback.html",
            categories=FEEDBACK_CATEGORIES,
            login_required_for_feedback=True,
        )

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if category not in FEEDBACK_CATEGORIES:
            flash("请选择有效的反馈类型。", "error")
            return render_template(
                "pages/feedback.html",
                categories=FEEDBACK_CATEGORIES,
            ), 400
        if not title:
            flash("请填写反馈标题。", "error")
            return render_template(
                "pages/feedback.html",
                categories=FEEDBACK_CATEGORIES,
            ), 400
        if len(title) > 120:
            flash("反馈标题不能超过 120 个字。", "error")
            return render_template(
                "pages/feedback.html",
                categories=FEEDBACK_CATEGORIES,
            ), 400
        if not content:
            flash("请填写反馈内容。", "error")
            return render_template(
                "pages/feedback.html",
                categories=FEEDBACK_CATEGORIES,
            ), 400
        if len(content) < 10 or len(content) > 1000:
            flash("反馈内容长度需要在 10 到 1000 个字之间。", "error")
            return render_template(
                "pages/feedback.html",
                categories=FEEDBACK_CATEGORIES,
            ), 400

        feedback_record = Feedback(
            user_id=user.id,
            category=category,
            title=title,
            content=content,
        )
        db.session.add(feedback_record)
        db.session.flush()

        admins = User.query.filter_by(role="admin").all()
        for admin in admins:
            create_notification(
                admin.id,
                "feedback_submitted",
                "收到新的问题反馈",
                f"用户 {user.username} 提交了新的问题反馈：{title}",
                "feedback_admin",
                feedback_record.id,
            )
        db.session.commit()
        flash("反馈已提交，管理员会在后台查看并回复。", "success")
        return redirect(url_for("pages.feedback"))

    return render_template("pages/feedback.html", categories=FEEDBACK_CATEGORIES)


@pages_bp.route("/my/feedback")
@login_required
def my_feedback():
    feedback_items = (
        Feedback.query.filter_by(user_id=session["user_id"])
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .all()
    )
    return render_template("pages/my_feedback.html", feedback_items=feedback_items)


@pages_bp.route("/my/feedback/<int:feedback_id>")
@login_required
def my_feedback_detail(feedback_id):
    feedback_item = Feedback.query.filter_by(
        id=feedback_id,
        user_id=session["user_id"],
    ).first_or_404()
    return render_template("pages/my_feedback_detail.html", feedback=feedback_item)


@pages_bp.route("/contact")
def contact():
    return render_template("pages/contact.html")


@pages_bp.route("/privacy")
def privacy():
    return render_template("pages/privacy.html")


@pages_bp.route("/terms")
def terms():
    return render_template("pages/terms.html")
