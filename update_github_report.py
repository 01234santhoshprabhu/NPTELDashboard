import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


BASE_DIR = Path(__file__).resolve().parent
COURSES_CSV = BASE_DIR / "courses.csv"
DOCS_DIR = BASE_DIR / "docs"
REPORT_CSV = DOCS_DIR / "enrollment_report.csv"
SUMMARY_JSON = DOCS_DIR / "summary.json"
MAX_WORKERS = int(os.getenv("NPTEL_REFRESH_WORKERS", "24"))
REQUEST_TIMEOUT = int(os.getenv("NPTEL_REQUEST_TIMEOUT", "8"))
RETRY_ATTEMPTS = int(os.getenv("NPTEL_RETRY_ATTEMPTS", "2"))
SECOND_PASS_DELAY_SECONDS = float(os.getenv("NPTEL_RETRY_DELAY_SECONDS", "0.25"))


def extract_course_id(url):
    match = re.search(r"(noc\d{2}_[a-z]+\d+)", str(url), re.IGNORECASE)
    if match:
        return match.group(1)
    return str(url).rstrip("/").split("/")[-1]


def fetch_count(course_id):
    api_url = (
        "https://onlinecourses.nptel.ac.in/e-learning/api/coursepreview"
        f"?course_id={course_id}"
    )
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.get(
                api_url,
                timeout=REQUEST_TIMEOUT,
                verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            data = response.json()
            if response.status_code == 404 or data.get("status") == 404:
                return course_id, "Removed / Unavailable", "Removed / Unavailable"
            payload = data.get("payload", {})
            if isinstance(payload, str):
                payload = json.loads(payload)
            student_count = payload.get("student_count")
            exam_registration_count = payload.get("exam_registrations_count")
            if student_count is None:
                last_error = "student_count missing"
                if attempt + 1 < RETRY_ATTEMPTS:
                    time.sleep(SECOND_PASS_DELAY_SECONDS)
                continue
            if exam_registration_count is None:
                exam_registration_count = 0
            return course_id, int(student_count), int(exam_registration_count)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < RETRY_ATTEMPTS:
                time.sleep(SECOND_PASS_DELAY_SECONDS)
    return course_id, f"Temporary Error: {last_error}", f"Temporary Error: {last_error}"


def load_previous_counts():
    if not REPORT_CSV.exists():
        return {}, {}
    try:
        old_df = pd.read_csv(REPORT_CSV)
        old_df = old_df[old_df["Course_ID"].astype(str).ne("TOTAL")]
        old_enrollment_values = pd.to_numeric(old_df["Learners_Enrolled"], errors="coerce")
        old_exam_values = pd.to_numeric(
            old_df.get("Exam_Registration", pd.Series(index=old_df.index, dtype="object")),
            errors="coerce",
        )
        previous_enrollment = {
            str(row["Course_ID"]): int(old_enrollment_values.loc[index])
            for index, row in old_df.iterrows()
            if pd.notna(old_enrollment_values.loc[index])
        }
        previous_exam = {
            str(row["Course_ID"]): int(old_exam_values.loc[index])
            for index, row in old_df.iterrows()
            if pd.notna(old_exam_values.loc[index])
        }
        return previous_enrollment, previous_exam
    except Exception:
        return {}, {}


def format_count_value(value):
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.notna(numeric_value):
        return int(numeric_value)
    return value


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(COURSES_CSV)
    df["Course_ID"] = df["Course_URL"].apply(extract_course_id)
    previous_enrollment_counts, previous_exam_counts = load_previous_counts()

    enrollment_results = {}
    exam_results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_count, cid) for cid in df["Course_ID"]]
        for future in as_completed(futures):
            course_id, enrollment_count, exam_count = future.result()
            enrollment_results[course_id] = enrollment_count
            exam_results[course_id] = exam_count

    df["Learners_Enrolled"] = df["Course_ID"].map(enrollment_results)
    df["Exam_Registration"] = df["Course_ID"].map(exam_results)

    failed_mask = pd.to_numeric(df["Learners_Enrolled"], errors="coerce").isna()
    failed_course_ids = df.loc[failed_mask, "Course_ID"].tolist()
    for course_id in failed_course_ids:
        if SECOND_PASS_DELAY_SECONDS:
            time.sleep(SECOND_PASS_DELAY_SECONDS)
        _, enrollment_count, exam_count = fetch_count(course_id)
        enrollment_results[course_id] = enrollment_count
        exam_results[course_id] = exam_count

    df["Learners_Enrolled"] = df["Course_ID"].map(enrollment_results)
    df["Exam_Registration"] = df["Course_ID"].map(exam_results)

    temporary_error_mask = df["Learners_Enrolled"].astype(str).str.startswith("Temporary Error:")
    df.loc[temporary_error_mask, "Learners_Enrolled"] = df.loc[
        temporary_error_mask, "Course_ID"
    ].map(previous_enrollment_counts)
    df.loc[temporary_error_mask, "Exam_Registration"] = df.loc[
        temporary_error_mask, "Course_ID"
    ].map(previous_exam_counts)
    df["Learners_Enrolled"] = df["Learners_Enrolled"].fillna("Temporary Error / No Previous Count")
    df["Exam_Registration"] = df["Exam_Registration"].fillna("Temporary Error / No Previous Count")
    report_df = df[["Course_ID", "Learners_Enrolled", "Exam_Registration"]].copy()
    numeric = pd.to_numeric(report_df["Learners_Enrolled"], errors="coerce")
    exam_numeric = pd.to_numeric(report_df["Exam_Registration"], errors="coerce")
    total = int(numeric.fillna(0).sum())
    total_exam_registration = int(exam_numeric.fillna(0).sum())
    report_df["Learners_Enrolled"] = report_df["Learners_Enrolled"].map(format_count_value)
    report_df["Exam_Registration"] = report_df["Exam_Registration"].map(format_count_value)
    total_row = pd.DataFrame(
        [["TOTAL", total, total_exam_registration]],
        columns=["Course_ID", "Learners_Enrolled", "Exam_Registration"],
    )
    report_df = pd.concat([report_df, total_row], ignore_index=True)
    report_df.to_csv(REPORT_CSV, index=False)

    summary = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "course_count": int(len(df)),
        "numeric_count": int(numeric.notna().sum()),
        "error_count": int(numeric.isna().sum()),
        "total_enrollment": total,
        "exam_registration_numeric_count": int(exam_numeric.notna().sum()),
        "exam_registration_error_count": int(exam_numeric.isna().sum()),
        "total_exam_registration": total_exam_registration,
        "top_courses": [
            {
                "course_id": str(row["Course_ID"]),
                "count": int(row["_count"]),
                "exam_registration": int(row["_exam_count"])
                if pd.notna(row["_exam_count"])
                else None,
            }
            for _, row in (
                df.assign(_count=numeric, _exam_count=exam_numeric)
                .dropna(subset=["_count"])
                .sort_values("_count", ascending=False)
                .head(10)
                .iterrows()
            )
        ],
        "top_exam_registrations": [
            {
                "course_id": str(row["Course_ID"]),
                "exam_registration": int(row["_exam_count"]),
                "count": int(row["_count"]) if pd.notna(row["_count"]) else None,
            }
            for _, row in (
                df.assign(_count=numeric, _exam_count=exam_numeric)
                .dropna(subset=["_exam_count"])
                .sort_values("_exam_count", ascending=False)
                .head(10)
                .iterrows()
            )
        ],
        "errors": [
            {
                "course_id": str(row["Course_ID"]),
                "course_url": str(row["Course_URL"]),
                "status": str(row["Learners_Enrolled"]),
                "exam_registration_status": str(row["Exam_Registration"]),
            }
            for _, row in df[numeric.isna()].iterrows()
        ],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Updated {REPORT_CSV}")
    print(f"Total enrollment: {total}")
    print(f"Total exam registration: {total_exam_registration}")
    print(f"Temporary/missing enrollment rows: {int(numeric.isna().sum())}")


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()
