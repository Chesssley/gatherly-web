from datetime import datetime
import os
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models import Circle, CircleMember, Comment, CommentImage, Interaction, Post, PostImage, User, db
from app.routes.activity import OFFICIAL_INTEREST_TAGS
from app.utils.upload_utils import delete_saved_images, save_image_files, validate_image_files

circle_bp = Blueprint("circle", __name__)

POST_IMAGE_MAX_BYTES = 800 * 1024
POST_IMAGE_MAX_COUNT = 3
COMMENT_IMAGE_MAX_BYTES = 500 * 1024
COMMENT_IMAGE_MAX_COUNT = 1
POST_UPLOAD_SUBDIR = os.path.join("uploads", "posts")
COMMENT_UPLOAD_SUBDIR = os.path.join("uploads", "comments")
OFFICIAL_CIRCLE_SUFFIX = "同好圈"

_CIRCLE_DESCRIPTIONS = {
    "摄影影像": "聚合胶片摄影、相机维护、街头摄影、摄影展和桌面摄影等影像爱好者。",
    "运动户外": "覆盖骑行、徒步、露营、夜跑、飞盘、攀岩等线下运动与轻户外约伴。",
    "咖啡茶饮": "连接手冲咖啡、咖啡拉花、茶会品鉴和咖啡店探访爱好者。",
    "阅读出版": "围绕独立出版、读书会、二手书交换、写作交流和书店探访展开。",
    "手作艺术": "收纳陶艺、插画手账、手帐拼贴、香薰调香和其他手作体验。",
    "音乐演出": "发现 Livehouse、音乐节、黑胶唱片试听和小型音乐现场。",
    "观影戏剧": "组织观影交流、剧本围读、即兴戏剧和展演后的线下讨论。",
    "城市探索": "发起城市漫步、旧物市集、古着穿搭、博物馆看展和本地探访。",
    "游戏桌游": "包含桌游组局、独立游戏试玩、模型手办交流和轻松联机活动。",
    "科技数码": "面向开源技术、数码工具、创客实践和技术主题线下分享。",
    "美食烘焙": "聚合本地美食、烘焙试吃、食谱交流和周末探店计划。",
    "公益志愿": "连接社区服务、公益行动、环保活动和志愿者线下协作。",
}

_ACTIVE_LEVELS = ["高活跃", "稳定活跃", "新兴活跃"]


def _official_description(tag):
    return _CIRCLE_DESCRIPTIONS.get(tag, f"{tag}爱好者的官方同好圈。")


def _official_member_count(index):
    return 96 + index * 17 + (index % 5) * 23


def _official_post_count(index):
    return 12 + index * 3 + (index % 4) * 5


def _official_circle_name(tag):
    return tag


def _legacy_official_circle_name(tag):
    return f"{tag}{OFFICIAL_CIRCLE_SUFFIX}"


def _strip_official_suffix(name):
    if name and name.endswith(OFFICIAL_CIRCLE_SUFFIX):
        return name[: -len(OFFICIAL_CIRCLE_SUFFIX)]
    return name


def _is_admin(user):
    return bool(user and user.role == "admin")


def _ensure_circle_columns():
    if db.engine.dialect.name != "sqlite":
        return

    rows = db.session.execute(text("PRAGMA table_info(circle)")).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if "owner_id" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN owner_id INTEGER")
    if "announcement" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN announcement TEXT")
    if "pinned_post_id" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN pinned_post_id INTEGER")
    if "is_pinned" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0")
    if "pinned_at" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN pinned_at DATETIME")
    if "is_system" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT 0")
    if "member_count" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN member_count INTEGER NOT NULL DEFAULT 0")
    if "initial_member_count" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN initial_member_count INTEGER NOT NULL DEFAULT 0")
    if "updated_at" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN updated_at DATETIME")

    for statement in statements:
        db.session.execute(text(statement))
    member_rows = db.session.execute(text("PRAGMA table_info(circle_member)")).fetchall()
    member_columns = {row[1] for row in member_rows}
    if member_rows and "role" not in member_columns:
        db.session.execute(
            text("ALTER TABLE circle_member ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'member'")
        )
        statements.append("ALTER TABLE circle_member ADD COLUMN role")
    normalized_roles = 0
    legacy_role_count = 0
    if member_rows:
        legacy_role_count = db.session.execute(
            text("SELECT COUNT(*) FROM circle_member WHERE role = 'admin'")
        ).scalar()
    if legacy_role_count:
        normalized_roles = db.session.execute(
            text("UPDATE circle_member SET role = 'moderator' WHERE role = 'admin'")
        ).rowcount
    if rows and "initial_member_count" not in existing_columns:
        db.session.execute(
            text(
                """
                UPDATE circle
                SET initial_member_count = MAX(
                    member_count - (
                        SELECT COUNT(*)
                        FROM circle_member
                        WHERE circle_member.circle_id = circle.id
                          AND circle_member.status = 'active'
                    ),
                    0
                )
                """
            )
        )
    if rows and "updated_at" not in existing_columns:
        db.session.execute(text("UPDATE circle SET updated_at = created_at WHERE updated_at IS NULL"))
    if statements or normalized_roles:
        db.session.commit()


@circle_bp.before_app_request
def ensure_circle_schema():
    _ensure_circle_columns()


def _ensure_circle_image_tables():
    PostImage.__table__.create(db.engine, checkfirst=True)
    CommentImage.__table__.create(db.engine, checkfirst=True)


def _ensure_post_status_column():
    if db.engine.dialect.name != "sqlite":
        return

    rows = db.session.execute(text("PRAGMA table_info(post)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if "status" not in existing_columns:
        db.session.execute(text("ALTER TABLE post ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'published'"))
        db.session.commit()


def _ensure_comment_parent_column():
    if db.engine.dialect.name != "sqlite":
        return

    rows = db.session.execute(text("PRAGMA table_info(comment)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if "parent_id" not in existing_columns:
        db.session.execute(text("ALTER TABLE comment ADD COLUMN parent_id INTEGER"))
        db.session.commit()


def _sync_system_circles():
    try:
        _ensure_circle_columns()
        _ensure_circle_image_tables()
        _ensure_post_status_column()
        _ensure_comment_parent_column()
        for circle in Circle.query.filter_by(is_system=True).all():
            circle.name = _strip_official_suffix(circle.name)

        for index, tag in enumerate(OFFICIAL_INTEREST_TAGS, start=1):
            name = _official_circle_name(tag)
            circle = (
                Circle.query.filter(
                    Circle.is_system.is_(True),
                    Circle.name.in_([name, _legacy_official_circle_name(tag)]),
                ).first()
            )
            if circle is None:
                circle = Circle(name=name, tag=tag, is_system=True)
                db.session.add(circle)
            else:
                circle.name = name

            circle.description = _official_description(tag)
            circle.initial_member_count = max(
                circle.initial_member_count or 0,
                _official_member_count(index),
            )
            _refresh_member_count(circle)
        db.session.commit()
    except OperationalError:
        db.session.rollback()


def _build_mock_circles():
    circles = []
    for index, tag in enumerate(OFFICIAL_INTEREST_TAGS, start=1):
        member_count = _official_member_count(index)
        post_count = _official_post_count(index)
        circles.append(
            {
                "id": index,
                "name": _official_circle_name(tag),
                "tag": tag,
                "description": _official_description(tag),
                "active_level": _ACTIVE_LEVELS[index % len(_ACTIVE_LEVELS)],
                "member_count": member_count,
                "post_count": post_count,
                "members": member_count,
                "activity_count": 2 + index % 7,
                "is_system": True,
            }
        )
    return circles


mock_circles = _build_mock_circles()


def _current_user():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


def _is_member(circle_id, user_id=None):
    user_id = user_id or session.get("user_id")
    if not user_id:
        return False
    return (
        CircleMember.query.filter_by(
            circle_id=circle_id,
            user_id=user_id,
            status="active",
        ).first()
        is not None
    )


def _circle_member_role(circle_id, user_id):
    if not user_id:
        return None
    member = CircleMember.query.filter_by(
        circle_id=circle_id,
        user_id=user_id,
        status="active",
    ).first()
    return member.role if member else None


def _can_manage_circle(user, circle):
    if user is None:
        return False
    if user.role == "admin" or circle.owner_id == user.id:
        return True
    return _circle_member_role(circle.id, user.id) in {"owner", "moderator", "admin"}


def _is_circle_owner(user, circle):
    return bool(user and circle.owner_id == user.id)


def _can_manage_circle_content(user, circle, author_id):
    if user is None:
        return False
    if user.role == "admin":
        return True
    if author_id == user.id:
        return True
    return _can_manage_circle(user, circle)


def _can_view_circle(user, circle):
    return circle.status != "deleted" and (circle.status == "active" or _is_admin(user))


def _refresh_member_count(circle):
    active_member_count = CircleMember.query.filter_by(
        circle_id=circle.id,
        status="active",
    ).count()
    circle.member_count = max(circle.initial_member_count or 0, 0) + active_member_count


def _circle_post_count(circle):
    return Post.query.filter_by(circle_id=circle.id, status="published").count()


def _decorate_circle(circle):
    circle.active_level = "官方圈子" if circle.is_system else "自定义圈子"
    circle.post_count = _circle_post_count(circle)
    circle.can_post = _is_member(circle.id)
    return circle


def _get_circle(circle_id):
    _sync_system_circles()
    circle = Circle.query.get(circle_id)
    if circle is not None:
        return circle

    mock_circle = next((item for item in mock_circles if item["id"] == circle_id), None)
    if mock_circle is None:
        return None
    return SimpleNamespace(**mock_circle)


def _interaction_counts(target_type, target_id):
    rows = (
        db.session.query(Interaction.action_type, func.count(Interaction.id))
        .filter(Interaction.target_type == target_type, Interaction.target_id == target_id)
        .group_by(Interaction.action_type)
        .all()
    )
    counts = {"like": 0, "favorite": 0, "share": 0}
    counts.update({action: count for action, count in rows})
    return counts


def _user_interaction_states(user_id, target_type, target_id):
    if not user_id:
        return {"like": False, "favorite": False}

    rows = Interaction.query.filter(
        Interaction.user_id == user_id,
        Interaction.target_type == target_type,
        Interaction.target_id == target_id,
        Interaction.action_type.in_(["like", "favorite"]),
    ).all()
    actions = {row.action_type for row in rows}
    return {
        "like": "like" in actions,
        "favorite": "favorite" in actions,
    }


def _toggle_interaction(user_id, target_type, target_id, action):
    existing = Interaction.query.filter_by(
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        action_type=action,
    ).first()
    if existing is not None and action in {"like", "favorite"}:
        db.session.delete(existing)
        db.session.commit()
        return "removed"

    if existing is None:
        db.session.add(
            Interaction(
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                action_type=action,
            )
        )
        db.session.commit()
        return "added"

    return "unchanged"


def _build_comment_item(comment, current_user, circle, replies_by_parent, depth=0, include_hidden=False):
    is_published = comment.status == "published"
    is_visible = is_published or (include_hidden and comment.status == "hidden")
    return {
        "comment": comment,
        "is_deleted": not is_visible,
        "depth": min(depth, 3),
        "counts": _interaction_counts("comment", comment.id) if is_published else {"like": 0, "favorite": 0},
        "states": (
            _user_interaction_states(
                current_user.id if current_user else None,
                "comment",
                comment.id,
            )
            if is_published
            else {"like": False, "favorite": False}
        ),
        "can_delete": (
            is_published
            and _can_manage_circle_content(current_user, circle, comment.author_id)
        ),
        "replies": [
            _build_comment_item(
                reply,
                current_user,
                circle,
                replies_by_parent,
                depth + 1,
                include_hidden=include_hidden,
            )
            for reply in replies_by_parent.get(comment.id, [])
            if reply.status == "published" or (include_hidden and reply.status == "hidden")
        ],
    }


def _build_comment_threads(comments, current_user, circle, include_hidden=False):
    replies_by_parent = {}
    for comment in comments:
        if comment.parent_id is not None:
            replies_by_parent.setdefault(comment.parent_id, []).append(comment)

    root_comments = []
    for comment in comments:
        if comment.parent_id is not None:
            continue
        has_visible_replies = any(
            reply.status == "published" or (include_hidden and reply.status == "hidden")
            for reply in replies_by_parent.get(comment.id, [])
        )
        if comment.status == "published" or (include_hidden and comment.status == "hidden") or has_visible_replies:
            root_comments.append(
                _build_comment_item(
                    comment,
                    current_user,
                    circle,
                    replies_by_parent,
                    include_hidden=include_hidden,
                )
            )

    return root_comments


@circle_bp.route("/circles")
def circles():
    _sync_system_circles()
    circle_rows = (
        Circle.query.filter_by(status="active")
        .order_by(
            Circle.is_pinned.desc(),
            Circle.pinned_at.desc(),
            Circle.is_system.desc(),
            Circle.member_count.desc(),
            func.coalesce(Circle.updated_at, Circle.created_at).desc(),
            Circle.created_at.desc(),
        )
        .all()
    )
    decorated = [_decorate_circle(circle) for circle in circle_rows]
    return render_template("circle.html", circles=decorated)


@circle_bp.route("/circle")
def circle_list():
    return circles()


@circle_bp.route("/circle/create", methods=["GET", "POST"])
def create_circle():
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))

    is_admin = _is_admin(user)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        tag = request.form.get("tag", "").strip()
        description = request.form.get("description", "").strip()
        requested_type = request.form.get("circle_type", "custom").strip()
        wants_system_circle = requested_type in {"official", "system"}

        if not name or not description:
            flash("圈子名称和简介不能为空。", "error")
            return render_template("circle.html", circles=[], create_mode=True, is_admin=is_admin)
        if len(name) > 120:
            flash("圈子名称不能超过 120 个字符。", "error")
            return render_template("circle.html", circles=[], create_mode=True, is_admin=is_admin)
        if wants_system_circle and not is_admin:
            flash("只有管理员可以创建官方圈子。", "error")
            return render_template("circle.html", circles=[], create_mode=True, is_admin=is_admin)

        is_system = wants_system_circle and is_admin
        circle = Circle(
            name=_strip_official_suffix(name) if is_system else name,
            tag=tag or ("官方" if is_system else "自定义"),
            description=description,
            owner_id=user.id,
            is_system=is_system,
            initial_member_count=0,
            member_count=1,
        )
        db.session.add(circle)
        db.session.flush()
        db.session.add(CircleMember(circle_id=circle.id, user_id=user.id, role="owner"))
        try:
            db.session.commit()
            flash("同好圈创建成功，你已成为圈主。", "success")
            return redirect(url_for("circle.circle_detail", circle_id=circle.id))
        except IntegrityError:
            db.session.rollback()
            flash("创建失败，请换一个圈子名称后重试。", "error")

    return render_template("circle.html", circles=[], create_mode=True, is_admin=is_admin)


@circle_bp.route("/circle/<int:circle_id>")
def circle_detail(circle_id):
    circle = _get_circle(circle_id)
    if circle is None:
        flash("圈子不存在或已被删除。", "error")
        return redirect(url_for("circle.circles"))

    if not isinstance(circle, Circle):
        flash("该圈子还未完成初始化，请刷新后重试。", "error")
        return redirect(url_for("circle.circles"))

    current_user = _current_user()
    if not _can_view_circle(current_user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))

    _ensure_comment_parent_column()
    post_query = Post.query.filter_by(circle_id=circle.id)
    if _is_admin(current_user):
        post_query = post_query.filter(Post.status.in_(["published", "hidden"]))
    else:
        post_query = post_query.filter_by(status="published")
    posts = post_query.order_by(
        (Post.id == circle.pinned_post_id).desc(),
        Post.created_at.desc(),
    ).all()
    post_items = []
    for post in posts:
        comments = (
            Comment.query.filter_by(post_id=post.id)
            .order_by(Comment.created_at.asc())
            .all()
        )
        post_items.append(
            {
                "post": post,
                "is_pinned": post.id == circle.pinned_post_id,
                "counts": _interaction_counts("post", post.id),
                "states": _user_interaction_states(
                    current_user.id if current_user else None,
                    "post",
                    post.id,
                ),
                "can_delete": _can_manage_circle_content(current_user, circle, post.user_id),
                "comments": _build_comment_threads(
                    comments,
                    current_user,
                    circle,
                    include_hidden=_is_admin(current_user),
                ),
            }
        )
    active_members = (
        CircleMember.query.filter_by(circle_id=circle.id, status="active")
        .join(User, CircleMember.user_id == User.id)
        .order_by(User.nickname.asc(), User.username.asc())
        .all()
    )
    return render_template(
        "circle_detail.html",
        circle=_decorate_circle(circle),
        posts=post_items,
        current_user=current_user,
        is_member=_is_member(circle.id),
        can_manage_circle=_can_manage_circle(current_user, circle),
        is_circle_owner=_is_circle_owner(current_user, circle),
        circle_members=active_members,
    )


@circle_bp.route("/circle/<int:circle_id>/join", methods=["POST"])
def join_circle(circle_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再加入同好圈。", "error")
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get_or_404(circle_id)
    if circle.status != "active":
        flash("该同好圈暂不可加入。", "error")
        return redirect(url_for("circle.circles"))
    member = CircleMember.query.filter_by(circle_id=circle.id, user_id=user.id).first()
    if member is None:
        db.session.add(CircleMember(circle_id=circle.id, user_id=user.id, role="member"))
    elif member.status != "active":
        member.status = "active"
        member.role = "owner" if circle.owner_id == user.id else "member"
        member.updated_at = datetime.utcnow()
    else:
        flash("您已经加入该同好圈。", "info")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    _refresh_member_count(circle)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("您已经加入该同好圈。", "info")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    flash("已加入同好圈。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/leave", methods=["POST"])
def leave_circle(circle_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再退出同好圈。", "error")
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get(circle_id)
    if circle is None:
        flash("同好圈不存在或已被移除。", "error")
        return redirect(url_for("circle.circles"))

    member = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=user.id,
        status="active",
    ).first()
    if member is None:
        flash("您尚未加入该同好圈。", "info")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if circle.owner_id == user.id:
        flash("请先将圈主身份转移给其他成员，再退出圈子。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member.status = "inactive"
    member.role = "member"
    member.updated_at = datetime.utcnow()
    _refresh_member_count(circle)
    db.session.commit()
    flash("已退出同好圈。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/announcement", methods=["POST"])
def update_announcement(circle_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_manage_circle(user, circle):
        flash("没有权限编辑圈内公告。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    announcement = request.form.get("announcement", "").strip()
    if len(announcement) > 1000:
        flash("圈内公告不能超过 1000 个字符。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    circle.announcement = announcement or None
    db.session.commit()
    flash("圈内公告已更新。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/post/<int:post_id>/pin", methods=["POST"])
def toggle_pin_post(circle_id, post_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_manage_circle(user, circle):
        flash("没有权限置顶圈内帖子。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    post = Post.query.filter_by(id=post_id, circle_id=circle.id, status="published").first()
    if post is None:
        flash("只能置顶当前圈子内正常显示的帖子。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if circle.pinned_post_id == post.id:
        circle.pinned_post_id = None
        message = "已取消置顶帖子。"
    else:
        circle.pinned_post_id = post.id
        message = "帖子已置顶。"
    db.session.commit()
    flash(message, "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"post-{post.id}"))


@circle_bp.route("/circle/<int:circle_id>/member/<int:user_id>/role", methods=["POST"])
def update_circle_member_role(circle_id, user_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _is_circle_owner(user, circle):
        flash("只有圈主可以设置圈子管理员。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=user_id,
        status="active",
    ).first()
    if member is None:
        flash("只能管理当前圈内成员。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    if member.user_id == circle.owner_id:
        flash("圈主身份不能通过管理员设置修改。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    role = request.form.get("role", "").strip()
    if role not in {"moderator", "member"}:
        flash("不支持的圈内角色。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member.role = role
    db.session.commit()
    flash("圈子管理员设置已更新。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/transfer-owner", methods=["POST"])
def transfer_circle_owner(circle_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _is_circle_owner(user, circle):
        flash("只有圈主可以转移圈主身份。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    target_user_id = request.form.get("user_id", type=int)
    target = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=target_user_id,
        status="active",
    ).first()
    if target is None or target.user_id == circle.owner_id:
        flash("请选择其他圈内成员接任圈主。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    previous_owner = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=circle.owner_id,
        status="active",
    ).first()
    if previous_owner is not None:
        previous_owner.role = "member"
    target.role = "owner"
    circle.owner_id = target.user_id
    db.session.commit()
    flash("圈主身份已转移。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/post", methods=["GET", "POST"])
def create_post(circle_id):
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))

    circle = _get_circle(circle_id)
    if circle is None or not isinstance(circle, Circle):
        flash("圈子不存在或已被删除。", "error")
        return redirect(url_for("circle.circles"))

    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))

    if not _is_member(circle.id, user.id):
        flash("加入同好圈后才能发帖。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if request.method == "GET":
        return render_template("create_post.html", circle=circle)

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    post_type = "discussion"

    if not title or not content:
        flash("标题和内容不能为空。", "error")
        return render_template("create_post.html", circle=circle)
    if len(title) > 100:
        flash("标题长度不能超过 100 个字符。", "error")
        return render_template("create_post.html", circle=circle)

    try:
        validated_images = validate_image_files(
            request.files.getlist("images"),
            max_count=POST_IMAGE_MAX_COUNT,
            max_bytes=POST_IMAGE_MAX_BYTES,
        )
        image_paths = save_image_files(validated_images, POST_UPLOAD_SUBDIR)
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("create_post.html", circle=circle)

    post = Post(title=title, content=content, type=post_type, user_id=user.id, circle_id=circle.id)
    try:
        db.session.add(post)
        db.session.flush()
        for image_path in image_paths:
            db.session.add(PostImage(post_id=post.id, image_path=image_path))
        db.session.commit()
        flash("帖子发布成功。", "success")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    except Exception:
        db.session.rollback()
        delete_saved_images(image_paths)
        flash("发布失败，请稍后重试。", "error")
        return render_template("create_post.html", circle=circle)


@circle_bp.route("/circle/<int:circle_id>/post/<int:post_id>/comment", methods=["POST"])
def comment_post(circle_id, post_id):
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    _ensure_circle_image_tables()
    _ensure_post_status_column()
    _ensure_comment_parent_column()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))
    post = Post.query.filter_by(id=post_id, circle_id=circle_id, status="published").first_or_404()
    content = request.form.get("content", "").strip()
    parent_id = request.form.get("parent_id", type=int)
    parent_comment = None
    if parent_id:
        parent_comment = Comment.query.filter_by(
            id=parent_id,
            post_id=post.id,
            status="published",
        ).first()
        if parent_comment is None:
            flash("无法回复不存在或已删除的评论。", "error")
            return redirect(url_for("circle.circle_detail", circle_id=post.circle_id, _anchor=f"post-{post.id}"))

    try:
        validated_images = validate_image_files(
            request.files.getlist("images"),
            max_count=COMMENT_IMAGE_MAX_COUNT,
            max_bytes=COMMENT_IMAGE_MAX_BYTES,
        )
        image_paths = save_image_files(validated_images, COMMENT_UPLOAD_SUBDIR)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("circle.circle_detail", circle_id=post.circle_id))

    if not content and not image_paths:
        flash("评论内容不能为空。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=post.circle_id))

    comment = Comment(
        author_id=user.id,
        post_id=post.id,
        parent_id=parent_comment.id if parent_comment else None,
        content=content or " ",
    )
    try:
        db.session.add(comment)
        db.session.flush()
        for image_path in image_paths:
            db.session.add(CommentImage(comment_id=comment.id, image_path=image_path))
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_saved_images(image_paths)
        flash("评论发布失败，请稍后重试。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=post.circle_id))
    flash("回复已发布。" if parent_comment else "评论已发布。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=post.circle_id, _anchor=f"comment-{comment.id}"))


@circle_bp.route("/circle/post/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再删除内容。", "error")
        return redirect(url_for("auth.login"))

    _ensure_post_status_column()
    post = Post.query.get_or_404(post_id)
    circle = Circle.query.get_or_404(post.circle_id)
    if not _can_manage_circle_content(user, circle, post.user_id):
        flash("没有权限删除该内容。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"post-{post.id}"))

    if circle.pinned_post_id == post.id:
        circle.pinned_post_id = None
    post.status = "deleted"
    db.session.commit()
    flash("帖子已删除。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/comment/<int:comment_id>/delete", methods=["POST"])
def delete_comment(comment_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再删除内容。", "error")
        return redirect(url_for("auth.login"))

    comment = Comment.query.get_or_404(comment_id)
    post = Post.query.get_or_404(comment.post_id)
    circle = Circle.query.get_or_404(post.circle_id)
    if not _can_manage_circle_content(user, circle, comment.author_id):
        flash("没有权限删除该内容。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"comment-{comment.id}"))

    comment.status = "deleted"
    db.session.commit()
    flash("评论已删除。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"post-{post.id}"))


@circle_bp.route("/circle/<int:circle_id>/post/<int:post_id>/interact/<action>", methods=["POST"])
def interact_post(circle_id, post_id, action):
    if action not in {"like", "favorite", "share"}:
        flash("不支持的互动类型。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle_id))

    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    _ensure_post_status_column()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))
    Post.query.filter_by(id=post_id, circle_id=circle_id, status="published").first_or_404()
    _toggle_interaction(user.id, "post", post_id, action)
    flash("操作已记录。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle_id, _anchor=f"post-{post_id}"))


@circle_bp.route("/circle/<int:circle_id>/comment/<int:comment_id>/interact/<action>", methods=["POST"])
def interact_comment(circle_id, comment_id, action):
    if action not in {"like", "favorite"}:
        flash("不支持的互动类型。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle_id))

    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get_or_404(circle_id)
    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))

    comment = (
        Comment.query.join(Post, Comment.post_id == Post.id)
        .filter(
            Comment.id == comment_id,
            Comment.status == "published",
            Post.circle_id == circle_id,
            Post.status == "published",
        )
        .first_or_404()
    )
    _toggle_interaction(user.id, "comment", comment.id, action)
    flash("操作已记录。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle_id, _anchor=f"comment-{comment.id}"))
