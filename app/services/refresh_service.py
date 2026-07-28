import subprocess
import sys
from datetime import date
from pathlib import Path

from app.extensions import db
from app.models import SchedulerLog, utcnow
from app.services.enrollment_service import EnrollmentImportService


class DailyRefreshService:
    """Run the existing enrollment refresh and persist the daily database snapshot."""

    def __init__(self, base_dir=None, importer=None, runner=None):
        """Create a refresh service with injectable dependencies for tests."""
        self.base_dir = Path(base_dir or Path(__file__).resolve().parents[2])
        self.importer = importer or EnrollmentImportService()
        self.runner = runner or subprocess.run

    def run(self, snapshot_date=None):
        """Run update_github_report.py and import its CSV output into history."""
        started = utcnow()
        log = SchedulerLog(job_name="daily_enrollment_refresh", status="running", started_at=started)
        db.session.add(log)
        db.session.commit()

        try:
            completed = self.runner(
                [sys.executable, "update_github_report.py"],
                cwd=str(self.base_dir),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            output = (completed.stdout or "").strip()
            if completed.returncode != 0:
                raise RuntimeError(output or f"Refresh failed with code {completed.returncode}")

            report_path = self.base_dir / "docs" / "enrollment_report.csv"
            result = self.importer.import_report(report_path, snapshot_date=snapshot_date or date.today(), source="daily_scheduler")
            log.status = "success"
            log.message = f"Imported {result['imported']} rows. {output}".strip()
            return result
        except Exception as exc:
            db.session.rollback()
            log = SchedulerLog.query.get(log.id) or log
            log.status = "failed"
            log.message = str(exc)
            raise
        finally:
            log.finished_at = utcnow()
            db.session.add(log)
            db.session.commit()
