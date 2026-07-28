import unittest

from app import create_app
from app.config import Config
from app.database import init_database
from app.extensions import db
from app.models import DailyEnrollmentHistory


class AdminToolsTestConfig(Config):
    """Test configuration for admin tools."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"


class AdminToolsRouteTest(unittest.TestCase):
    """Coverage for operational admin tools."""

    def setUp(self):
        """Create app, seed admin, and log in."""
        self.app = create_app(AdminToolsTestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        init_database("admin@example.com", "secret123")
        self.client = self.app.test_client()
        self.client.post("/login", data={"email": "admin@example.com", "password": "secret123"})

    def tearDown(self):
        """Clean up database and context."""
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_tools_page_lists_full_app_tools(self):
        """Verify admin tools page exposes the core application modules."""
        response = self.client.get("/admin/tools")
        self.assertEqual(response.status_code, 200)
        for label in [b"Count Dashboard", b"User Management", b"REST APIs", b"Scheduler", b"Exports"]:
            self.assertIn(label, response.data)

    def test_import_current_csv_tool_imports_history(self):
        """Verify current displayed CSV can be imported from the tools page."""
        response = self.client.post("/admin/import-current")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Import Complete", response.data)
        self.assertGreater(DailyEnrollmentHistory.query.count(), 1000)


if __name__ == "__main__":
    unittest.main()
