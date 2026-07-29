import unittest
from unittest.mock import patch

from app import create_app
from app.config import Config
from app.database import init_database
from app.extensions import db
from app.models import DailyEnrollmentHistory, SchedulerLog


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
        for label in [b"Count Dashboard", b"User Management", b"REST APIs", b"Scheduler", b"Exports", b"Database", b"Member Count Sync", b"Update Drive"]:
            self.assertIn(label, response.data)

    def test_import_current_csv_tool_imports_history(self):
        """Verify current displayed CSV can be imported from the tools page."""
        response = self.client.post("/admin/import-current")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Import Complete", response.data)
        self.assertGreater(DailyEnrollmentHistory.query.count(), 1000)


    @patch("app.routes.admin.DashboardPublishService.publish_current_dashboard_files", side_effect=RuntimeError("GitHub publish not configured. Set GITHUB_PUBLISH_TOKEN in Render Environment."))
    @patch("app.routes.admin.DashboardPublishService.rebuild_summary_from_csv", return_value={"total_enrollment": 123})
    def test_import_current_drive_imports_db_and_reports_missing_token(self, _summary, _publish):
        """Verify current CSV import plus drive update reports missing GitHub configuration."""
        response = self.client.post("/admin/import-current-drive")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CSV Imported", response.data)
        self.assertIn(b"GITHUB_PUBLISH_TOKEN", response.data)
        self.assertGreater(DailyEnrollmentHistory.query.count(), 1000)


    def test_tools_page_repairs_stale_running_logs(self):
        """Verify stale running refresh logs are marked failed."""
        from datetime import datetime, timedelta, timezone

        db.session.add(SchedulerLog(job_name="daily_enrollment_refresh", status="running", started_at=datetime.now(timezone.utc) - timedelta(hours=2)))
        db.session.commit()
        response = self.client.get("/admin/tools")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SchedulerLog.query.first().status, "failed")

    def test_sync_members_runs_from_tools(self):
        """Verify member count sync can be started from the tools page."""
        response = self.client.post("/admin/sync-members", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"member_count_sync", response.data)


if __name__ == "__main__":
    unittest.main()
