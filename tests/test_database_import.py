import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.database import init_database
from app.extensions import db
from app.models import Course, DailyEnrollmentHistory, Role, User
from app.services.enrollment_service import EnrollmentImportService


class TestConfig(Config):
    """Test configuration using a temporary SQLite database."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"


class DatabaseImportTest(unittest.TestCase):
    """Coverage for schema initialization and enrollment imports."""

    def setUp(self):
        """Create a clean application database for each test."""
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        """Remove the application context after each test."""
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_init_database_creates_roles_and_admin(self):
        """Verify default roles, permissions, and admin user are seeded."""
        init_database("admin@example.com", "secret123")
        self.assertEqual(Role.query.count(), 4)
        user = User.query.filter_by(email="admin@example.com").first()
        self.assertIsNotNone(user)
        self.assertTrue(user.check_password("secret123"))
        self.assertTrue(user.has_permission("users.manage"))

    def test_import_report_upserts_daily_history(self):
        """Verify CSV enrollment reports create course and history records."""
        directory = Path(".test_tmp")
        directory.mkdir(exist_ok=True)
        report = directory / "report.csv"
        report.write_text(
            "Course_ID,Learners_Enrolled,Exam_Registration\n"
            "noc26_cs01,100,25\n"
            "noc26_cs02,Removed / Unavailable,0\n"
            "TOTAL,100,25\n",
            encoding="utf-8",
        )
        result = EnrollmentImportService().import_report(report)

        self.assertEqual(result["imported"], 2)
        self.assertEqual(Course.query.count(), 2)
        self.assertEqual(DailyEnrollmentHistory.query.count(), 2)
        removed = Course.query.filter_by(course_id="noc26_cs02").first().daily_history.first()
        self.assertIsNone(removed.learners_enrolled)
        self.assertEqual(removed.raw_enrollment_status, "Removed / Unavailable")


if __name__ == "__main__":
    unittest.main()


