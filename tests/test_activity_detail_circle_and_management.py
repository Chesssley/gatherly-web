import unittest
from datetime import datetime, timedelta

from app import create_app
from app.models import Activity, AdminLog, Circle, CircleRating, User, db


class ActivityDetailCircleAndManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.admin = User(
            username="admin_user",
            email="admin@example.com",
            password_hash="scrypt:test",
            role="admin",
        )
        self.organizer = User(
            username="organizer_user",
            email="organizer@example.com",
            password_hash="scrypt:test",
        )
        self.user = User(
            username="regular_user",
            email="regular@example.com",
            password_hash="scrypt:test",
        )
        self.circle = Circle(name="电影同好圈", tag="观影戏剧", status="active")
        db.session.add_all([self.admin, self.organizer, self.user, self.circle])
        db.session.commit()

        self.original_start = datetime(2030, 5, 1, 10, 0)
        self.original_end = self.original_start + timedelta(hours=2)
        self.activity = Activity(
            title="圈子跳转测试活动",
            description="活动简介",
            detail="活动详情",
            city="上海",
            location="活动地点",
            start_time=self.original_start,
            end_time=self.original_end,
            circle_id=self.circle.id,
            organizer_id=self.organizer.id,
            status="open",
        )
        db.session.add(self.activity)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, user):
        with self.client.session_transaction() as session:
            session["user_id"] = user.id

    def _post_update_time(self, start_time, end_time, follow_redirects=False):
        return self.client.post(
            f"/activity/{self.activity.id}/admin/update-time",
            data={
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M"),
                "end_time": end_time.strftime("%Y-%m-%dT%H:%M"),
            },
            follow_redirects=follow_redirects,
        )

    def test_activity_circle_link_opens_circle_detail_with_rating_area(self):
        response = self.client.get(f"/activity/{self.activity.id}")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"/circle/{self.circle.id}#circle-ratings", html)

        response = self.client.get(f"/circle/{self.circle.id}")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("圈子评分", html)

    def test_activity_without_circle_does_not_render_circle_link(self):
        activity = Activity(
            title="无圈子活动",
            description="活动简介",
            detail="活动详情",
            city="上海",
            location="活动地点",
            start_time=self.original_start,
            end_time=self.original_end,
            organizer_id=self.organizer.id,
            status="open",
        )
        db.session.add(activity)
        db.session.commit()

        response = self.client.get(f"/activity/{activity.id}")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("所属同好圈", html)

    def test_missing_circle_id_uses_friendly_redirect(self):
        response = self.client.get("/circle/999999")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/circles", response.headers["Location"])

    def test_circle_detail_review_with_activity_without_start_time_does_not_500(self):
        no_time_activity = Activity(
            title="无开始时间活动",
            description="活动简介",
            detail="活动详情",
            city="上海",
            location="活动地点",
            start_time=None,
            end_time=None,
            circle_id=self.circle.id,
            organizer_id=self.organizer.id,
            status="open",
        )
        db.session.add(no_time_activity)
        db.session.commit()
        db.session.add(
            CircleRating(
                circle_id=self.circle.id,
                user_id=self.user.id,
                activity_id=no_time_activity.id,
                rating=5,
                comment="活动很好。",
            )
        )
        db.session.commit()

        response = self.client.get(f"/circle/{self.circle.id}")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("无开始时间活动", html)
        self.assertIn("活动时间待补充", html)

    def test_management_panel_visibility_by_role(self):
        self._login(self.user)
        response = self.client.get(f"/activity/{self.activity.id}")
        html = response.get_data(as_text=True)
        self.assertNotIn("活动管理", html)
        self.assertNotIn("发起人管理", html)
        self.assertNotIn("保存活动时间", html)

        self._login(self.organizer)
        response = self.client.get(f"/activity/{self.activity.id}")
        html = response.get_data(as_text=True)
        self.assertIn("活动管理", html)
        self.assertIn("发起人管理", html)
        self.assertNotIn("保存活动时间", html)

        self._login(self.admin)
        response = self.client.get(f"/activity/{self.activity.id}")
        html = response.get_data(as_text=True)
        self.assertIn("活动管理", html)
        self.assertIn("发起人管理", html)
        self.assertIn("活动时间管理", html)
        self.assertIn("保存活动时间", html)

    def test_regular_user_direct_time_update_post_is_rejected(self):
        self._login(self.user)
        new_start = datetime(2030, 5, 2, 14, 0)
        new_end = new_start + timedelta(hours=3)

        response = self._post_update_time(new_start, new_end)

        self.assertEqual(response.status_code, 403)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.start_time, self.original_start)
        self.assertEqual(self.activity.end_time, self.original_end)

    def test_invalid_time_range_does_not_save(self):
        self._login(self.admin)
        invalid_start = datetime(2030, 5, 2, 14, 0)
        invalid_end = datetime(2030, 5, 2, 13, 0)

        response = self._post_update_time(invalid_start, invalid_end, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.start_time, self.original_start)
        self.assertEqual(self.activity.end_time, self.original_end)
        self.assertEqual(AdminLog.query.count(), 0)

    def test_invalid_time_format_does_not_500_or_save(self):
        self._login(self.admin)

        response = self.client.post(
            f"/activity/{self.activity.id}/admin/update-time",
            data={
                "start_time": "2030-05-02",
                "end_time": "not-a-time",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.start_time, self.original_start)
        self.assertEqual(self.activity.end_time, self.original_end)
        self.assertEqual(AdminLog.query.count(), 0)

    def test_system_admin_can_update_closed_activity_time(self):
        self.activity.status = "closed"
        db.session.commit()
        self._login(self.admin)
        new_start = datetime(2030, 5, 3, 9, 30)
        new_end = datetime(2030, 5, 3, 12, 0)

        response = self._post_update_time(new_start, new_end, follow_redirects=True)
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.status, "open")
        self.assertEqual(self.activity.start_time, new_start)
        self.assertEqual(self.activity.end_time, new_end)
        self.assertIn(new_start.strftime("%Y-%m-%d %H:%M"), html)
        self.assertEqual(AdminLog.query.filter_by(action="update_activity_time").count(), 1)


if __name__ == "__main__":
    unittest.main()
