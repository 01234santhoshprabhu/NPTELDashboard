import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from app.extensions import db
from app.models import SchedulerLog, utcnow
from app.services.enrollment_service import EnrollmentImportService


class DailyRefreshService:
    """Run existing refresh jobs and persist database snapshots."""

    def __init__(self, base_dir=None, importer=None, runner=None):
        """Create a refresh service with injectable dependencies for tests."""
        self.base_dir = Path(base_dir or Path(__file__).resolve().parents[2])
        self.importer = importer or EnrollmentImportService()
        self.runner = runner or subprocess.run

    def run(self, snapshot_date=None, log_id=None):
        """Run update_github_report.py and import its CSV output into history."""
        log = self._get_or_create_log("daily_enrollment_refresh", log_id)
        try:
            completed = self.runner(
                [sys.executable, "update_github_report.py"],
                cwd=str(self.base_dir),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=None,
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
            log = db.session.get(SchedulerLog, log.id) or log
            log.status = "failed"
            log.message = str(exc)
            raise
        finally:
            log.finished_at = utcnow()
            db.session.add(log)
            db.session.commit()

    def sync_member_files(self, log_id=None):
        """Copy latest member count outputs into docs for the dashboard."""
        log = self._get_or_create_log("member_count_sync", log_id)
        source_dir = self.base_dir.parent / "member_test" / "output"
        mappings = {
            "summary_test.json": "member_summary.json",
            "member_counts_test.csv": "member_counts.csv",
        }
        try:
            copied = []
            for source_name, target_name in mappings.items():
                source = source_dir / source_name
                if not source.exists():
                    raise FileNotFoundError(f"Missing member output: {source}")
                target = self.base_dir / "docs" / target_name
                shutil.copyfile(source, target)
                copied.append(target_name)
            log.status = "success"
            log.message = "Synced " + ", ".join(copied)
            return {"copied": copied}
        except Exception as exc:
            db.session.rollback()
            log = db.session.get(SchedulerLog, log.id) or log
            log.status = "failed"
            log.message = str(exc)
            raise
        finally:
            log.finished_at = utcnow()
            db.session.add(log)
            db.session.commit()

    def mark_stale_running_jobs_failed(self, older_than_minutes=30):
        """Mark old running logs as failed so the UI reflects reality."""
        cutoff = utcnow() - timedelta(minutes=older_than_minutes)
        logs = SchedulerLog.query.filter(SchedulerLog.status.in_(["queued", "running"]), SchedulerLog.started_at < cutoff).all()
        for log in logs:
            log.status = "failed"
            log.finished_at = utcnow()
            log.message = log.message or "Marked failed because the job became stale. Start a new refresh if needed."
        db.session.commit()
        return len(logs)

    def _get_or_create_log(self, job_name, log_id=None):
        """Return an existing scheduler log or create a running one."""
        log = db.session.get(SchedulerLog, log_id) if log_id else None
        if log is None:
            log = SchedulerLog(job_name=job_name, status="running", started_at=utcnow())
            db.session.add(log)
        log.job_name = job_name
        log.status = "running"
        log.finished_at = None
        db.session.commit()
        return log
