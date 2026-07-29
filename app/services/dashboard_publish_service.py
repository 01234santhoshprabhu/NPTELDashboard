import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


class DashboardPublishService:
    """Prepare dashboard files and optionally publish them back to GitHub."""

    DASHBOARD_FILES = [
        "docs/enrollment_report.csv",
        "docs/summary.json",
        "docs/member_summary.json",
        "docs/member_counts.csv",
        "docs/daily_log.json",
        "docs/test.html",
    ]

    def __init__(self, base_dir=None, http_client=None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parents[2])
        self.http = http_client or requests.Session()

    def rebuild_summary_from_csv(self):
        """Rebuild docs/summary.json from the current enrollment CSV."""
        report_path = self.base_dir / "docs" / "enrollment_report.csv"
        summary_path = self.base_dir / "docs" / "summary.json"
        if not report_path.exists():
            raise FileNotFoundError(f"Enrollment report not found: {report_path}")

        frame = pd.read_csv(report_path)
        frame = frame[frame["Course_ID"].astype(str).ne("TOTAL")].copy()
        enrollment_numeric = pd.to_numeric(frame["Learners_Enrolled"], errors="coerce")
        exam_numeric = pd.to_numeric(frame.get("Exam_Registration"), errors="coerce")
        total_enrollment = int(enrollment_numeric.fillna(0).sum())
        total_exam = int(exam_numeric.fillna(0).sum())

        summary = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "course_count": int(len(frame)),
            "numeric_count": int(enrollment_numeric.notna().sum()),
            "error_count": int(enrollment_numeric.isna().sum()),
            "total_enrollment": total_enrollment,
            "exam_registration_numeric_count": int(exam_numeric.notna().sum()),
            "exam_registration_error_count": int(exam_numeric.isna().sum()),
            "total_exam_registration": total_exam,
            "top_courses": self._top_rows(frame, enrollment_numeric, exam_numeric, "enrollment"),
            "top_exam_registrations": self._top_rows(frame, enrollment_numeric, exam_numeric, "exam"),
            "errors": [
                {
                    "course_id": str(row["Course_ID"]),
                    "status": str(row["Learners_Enrolled"]),
                    "exam_registration_status": str(row.get("Exam_Registration", "")),
                }
                for _, row in frame[enrollment_numeric.isna()].iterrows()
            ],
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    def publish_current_dashboard_files(self, message=None):
        """Publish current dashboard files to GitHub when credentials are configured."""
        token = os.getenv("GITHUB_PUBLISH_TOKEN") or os.getenv("GH_TOKEN")
        repository = os.getenv("GITHUB_REPOSITORY", "01234santhoshprabhu/NPTELDashboard")
        branch = os.getenv("GITHUB_PUBLISH_BRANCH", "main")
        if not token:
            raise RuntimeError("GitHub publish not configured. Set GITHUB_PUBLISH_TOKEN in Render Environment.")

        published = []
        for relative_path in self.DASHBOARD_FILES:
            local_path = self.base_dir / relative_path
            if not local_path.exists():
                continue
            self._put_github_file(
                repository=repository,
                branch=branch,
                relative_path=relative_path,
                local_path=local_path,
                token=token,
                message=message or "Update dashboard files from admin tools",
            )
            published.append(relative_path)
        return {"repository": repository, "branch": branch, "published": published}

    def _top_rows(self, frame, enrollment_numeric, exam_numeric, kind):
        if kind == "exam":
            sorted_rows = frame.assign(_count=enrollment_numeric, _exam_count=exam_numeric).dropna(subset=["_exam_count"]).sort_values("_exam_count", ascending=False).head(10)
            return [
                {
                    "course_id": str(row["Course_ID"]),
                    "exam_registration": int(row["_exam_count"]),
                    "count": int(row["_count"]) if pd.notna(row["_count"]) else None,
                }
                for _, row in sorted_rows.iterrows()
            ]
        sorted_rows = frame.assign(_count=enrollment_numeric, _exam_count=exam_numeric).dropna(subset=["_count"]).sort_values("_count", ascending=False).head(10)
        return [
            {
                "course_id": str(row["Course_ID"]),
                "count": int(row["_count"]),
                "exam_registration": int(row["_exam_count"]) if pd.notna(row["_exam_count"]) else None,
            }
            for _, row in sorted_rows.iterrows()
        ]

    def _put_github_file(self, repository, branch, relative_path, local_path, token, message):
        api_url = f"https://api.github.com/repos/{repository}/contents/{relative_path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        get_response = self.http.get(api_url, headers=headers, params={"ref": branch}, timeout=30)
        sha = None
        if get_response.status_code == 200:
            sha = get_response.json().get("sha")
        elif get_response.status_code != 404:
            raise RuntimeError(f"GitHub lookup failed for {relative_path}: {get_response.status_code} {get_response.text[:200]}")

        payload = {
            "message": message,
            "branch": branch,
            "content": base64.b64encode(local_path.read_bytes()).decode("ascii"),
        }
        if sha:
            payload["sha"] = sha
        put_response = self.http.put(api_url, headers=headers, json=payload, timeout=60)
        if put_response.status_code not in {200, 201}:
            raise RuntimeError(f"GitHub publish failed for {relative_path}: {put_response.status_code} {put_response.text[:200]}")
