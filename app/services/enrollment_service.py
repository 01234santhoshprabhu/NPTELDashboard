from datetime import date
from pathlib import Path

import pandas as pd

from app.extensions import db
from app.repositories import CourseRepository, EnrollmentHistoryRepository


class EnrollmentImportService:
    """Import enrollment reports into normalized database history."""

    def __init__(self, course_repository=None, history_repository=None):
        """Create an importer with replaceable repositories for testing."""
        self.course_repository = course_repository or CourseRepository()
        self.history_repository = history_repository or EnrollmentHistoryRepository()

    def import_report(self, report_path, snapshot_date=None, source="csv_import"):
        """Import a CSV report and return counts for processed rows."""
        path = Path(report_path)
        if not path.exists():
            raise FileNotFoundError(f"Enrollment report not found: {path}")

        snapshot = snapshot_date or date.today()
        frame = pd.read_csv(path)
        frame = frame[frame["Course_ID"].astype(str).ne("TOTAL")].copy()
        imported = 0
        errors = 0

        for _, row in frame.iterrows():
            course_code = str(row.get("Course_ID", "")).strip()
            if not course_code:
                errors += 1
                continue
            learners, raw_enrollment = self._parse_optional_int(row.get("Learners_Enrolled"))
            exam, raw_exam = self._parse_optional_int(row.get("Exam_Registration"))
            members, _ = self._parse_optional_int(row.get("Google_Members"))
            course = self.course_repository.get_or_create(course_code)
            self.history_repository.upsert_daily_snapshot(
                course=course,
                snapshot_date=snapshot,
                learners=learners,
                exam_registration=exam,
                members=members,
                raw_enrollment=raw_enrollment,
                raw_exam=raw_exam,
                source=source,
            )
            imported += 1

        db.session.commit()
        return {"imported": imported, "errors": errors, "snapshot_date": snapshot.isoformat()}

    def _parse_optional_int(self, value):
        """Convert numeric-looking values to int while preserving status strings."""
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.notna(numeric):
            return int(numeric), None
        if value is None or str(value).strip() == "":
            return None, None
        return None, str(value)
