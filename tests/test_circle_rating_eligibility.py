import unittest
from datetime import datetime, timedelta

from app import create_app
from app.models import Activity, Circle, CircleRating, Registration, User, db


class CircleRatingEligibilityTestCase(unittest.TestCase):
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

        self.user = User(
            username="rating_user",
            email="rating_user@example.com",
            password_hash="scrypt:test",
        )
        self.organizer = User(
            username="organizer",
            email="organizer@example.com",
            password_hash="scrypt:test",
        )
        self.circle = Circle(name="电影同好圈", tag="观影戏剧")
        db.session.add_all([self.user, self.organizer, self.circle])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        with self.client.session_transaction() as session:
            session["user_id"] = self.user.id

    def _activity(self, title, start_time):
        activity = Activity(
            title=title,
            description="活动简介",
            city="上海",
            location="活动地点",
            start_time=start_time,
            end_time=start_time + timedelta(hours=2),
            circle_id=self.circle.id,
            organizer_id=self.organizer.id,
        )
        db.session.add(activity)
        db.session.commit()
        return activity

    def _register(self, activity):
        db.session.add(Registration(user_id=self.user.id, activity_id=activity.id))
        db.session.commit()

    def test_future_circle_activity_does_not_allow_rating(self):
        future_activity = self._activity("尚未开始的活动", datetime.now() + timedelta(days=1))
        self._register(future_activity)
        self._login()

        response = self.client.post(
            f"/circle/{self.circle.id}/ratings",
            data={
                "activity_id": str(future_activity.id),
                "rating": "5",
                "comment": "期待活动",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("该活动尚未开始，活动开始后才可以评分。", response.get_data(as_text=True))
        self.assertIsNone(CircleRating.query.filter_by(user_id=self.user.id).first())

    def test_future_registered_circle_activity_is_visible_but_marked_pending(self):
        future_activity = self._activity("尚未开始的活动", datetime.now() + timedelta(days=1))
        self._register(future_activity)
        self._login()

        response = self.client.get(f"/circle/{self.circle.id}")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("尚未开始的活动", html)
        self.assertIn("未开始", html)
        self.assertIn("data-can-rate=\"false\"", html)

    def test_started_circle_activity_allows_rating_and_binds_activity(self):
        started_activity = self._activity("独立电影放映与交流夜", datetime.now() - timedelta(hours=1))
        self._register(started_activity)
        self._login()

        response = self.client.post(
            f"/circle/{self.circle.id}/ratings",
            data={
                "activity_id": str(started_activity.id),
                "rating": "4",
                "comment": "活动之后再评价，体验真实。",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        rating = CircleRating.query.filter_by(user_id=self.user.id, circle_id=self.circle.id).one()
        self.assertEqual(rating.activity_id, started_activity.id)
        self.assertEqual(rating.rating, 4)

    def test_registered_started_activity_is_visible_and_marked_rateable(self):
        started_activity = self._activity("独立电影放映与交流夜", datetime.now() - timedelta(hours=1))
        self._register(started_activity)
        self._login()

        response = self.client.get(f"/circle/{self.circle.id}")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("独立电影放映与交流夜", html)
        self.assertIn("可评价", html)
        self.assertIn("data-can-rate=\"true\"", html)

    def test_registered_activity_from_another_circle_cannot_be_used_for_rating(self):
        other_circle = Circle(name="读书同好圈", tag="阅读出版")
        db.session.add(other_circle)
        db.session.commit()
        other_activity = Activity(
            title="另一圈活动",
            description="活动简介",
            city="上海",
            location="活动地点",
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
            circle_id=other_circle.id,
            organizer_id=self.organizer.id,
        )
        valid_activity = self._activity("本圈活动", datetime.now() - timedelta(hours=1))
        db.session.add(other_activity)
        db.session.commit()
        self._register(other_activity)
        self._register(valid_activity)
        self._login()

        response = self.client.post(
            f"/circle/{self.circle.id}/ratings",
            data={
                "activity_id": str(other_activity.id),
                "rating": "5",
                "comment": "不能串圈评价。",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("请选择你已报名的圈子关联活动。", response.get_data(as_text=True))
        self.assertIsNone(CircleRating.query.filter_by(user_id=self.user.id, circle_id=self.circle.id).first())

    def test_rating_review_shows_bound_activity(self):
        started_activity = self._activity("独立电影放映与交流夜", datetime.now() - timedelta(days=1))
        self._register(started_activity)
        db.session.add(
            CircleRating(
                circle_id=self.circle.id,
                user_id=self.user.id,
                activity_id=started_activity.id,
                rating=5,
                comment="现场交流很顺畅。",
            )
        )
        db.session.commit()

        response = self.client.get(f"/circle/{self.circle.id}")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("独立电影放映与交流夜", html)
        self.assertIn(f"{started_activity.start_time.year}年{started_activity.start_time.month}月", html)


if __name__ == "__main__":
    unittest.main()
