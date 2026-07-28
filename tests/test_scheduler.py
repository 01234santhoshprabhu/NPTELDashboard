import subprocess
import unittest
from datetime import date
from types import SimpleNamespace

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import SchedulerLog


class SchedulerTestConfig(Config):
    """Test configuration for scheduler service."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"


class FakeImporter:
    """Importer test double that records import requests."""

    def __init__(self):
        """Initialize import call storage."""
        self.calls = []

    def import_report(self, report_path, snapshot_date=None, source="csv_import"):
        """Record an import and return a successful result."""
        self.calls.append((str(report_path), snapshot_date, source))
        return {"imported": 3, "errors": 0, "snapshot_date": snapshot_date.isoformat()}


class SchedulerServiceTest(unittest.TestCase):
    """Coverage for the daily refresh scheduler service."""

    def setUp(self):
        """Create a clean in-memory application."""
        self.app = create_app(SchedulerTestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        """Clean up the application context."""
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_refresh_service_logs_success(self):
        """Verify the refresh service runs the existing script and logs success."""
        from app.services.refresh_service import DailyRefreshService

        importer = FakeImporter()

        def runner(command, cwd, text, stdout, stderr, timeout=None):
            self.assertIn("update_github_report.py", command)
            self.assertEqual(stdout, subprocess.PIPE)
            return SimpleNamespace(returncode=0, stdout="ok")

        result = DailyRefreshService(importer=importer, runner=runner).run(snapshot_date=date(2026, 7, 28))

        self.assertEqual(result["imported"], 3)
        self.assertEqual(SchedulerLog.query.count(), 1)
        self.assertEqual(SchedulerLog.query.first().status, "success")
        self.assertEqual(importer.calls[0][2], "daily_scheduler")


    def test_create_five_minute_scheduler(self):
        """Verify local scheduler can be configured for 5-minute refreshes."""
        from app.scheduler import create_scheduler

        scheduler = create_scheduler(self.app, every_5_minutes=True)
        jobs = scheduler.get_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].id, "five_minute_dashboard_refresh")
        self.assertIn("interval", str(jobs[0].trigger))


if __name__ == "__main__":
    unittest.main()


