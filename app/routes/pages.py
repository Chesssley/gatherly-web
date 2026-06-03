from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/community-guidelines")
def community_guidelines():
    return render_template("pages/community_guidelines.html")


@pages_bp.route("/safety-tips")
def safety_tips():
    return render_template("pages/safety_tips.html")


@pages_bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        feedback_type = request.form.get("feedback_type", "").strip() or "其他建议"
        contact = request.form.get("contact", "").strip()
        content = request.form.get("content", "").strip()

        if not content:
            flash("请填写反馈内容。", "error")
            return render_template("pages/feedback.html"), 400
        if len(content) < 10 or len(content) > 1000:
            flash("反馈内容长度建议在 10 到 1000 个字之间。", "error")
            return render_template("pages/feedback.html"), 400

        current_app.logger.info(
            "Feedback submitted: type=%s, content_length=%s, contact_provided=%s",
            feedback_type,
            len(content),
            bool(contact),
        )
        flash("感谢你的反馈，我们会在后续迭代中查看。", "success")
        return redirect(url_for("pages.feedback"))

    return render_template("pages/feedback.html")


@pages_bp.route("/contact")
def contact():
    return render_template("pages/contact.html")


@pages_bp.route("/privacy")
def privacy():
    return render_template("pages/privacy.html")


@pages_bp.route("/terms")
def terms():
    return render_template("pages/terms.html")
