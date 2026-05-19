from flask import Blueprint, render_template_string

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
def admin_dashboard():
    return render_template_string(
        """
        {% extends "base.html" %}
        {% block title %}后台管理 - Gatherly{% endblock %}
        {% block content %}
        <section class="section">
          <div class="container page-title">
            <p class="eyebrow">Admin</p>
            <h1>后台管理</h1>
            <p>这里是 Gatherly 后台占位页，后续可接入活动审核、用户管理和内容管理功能。</p>
          </div>
        </section>
        {% endblock %}
        """
    )
