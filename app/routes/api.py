from flask import Blueprint, jsonify

from app.models import Course, DailyEnrollmentHistory


api_bp = Blueprint("api", __name__)


@api_bp.route("/courses")
def courses():
    """Return course catalog records for API clients."""
    rows = Course.query.order_by(Course.course_id.asc()).limit(500).all()
    return jsonify([{"course_id": row.course_id, "status": row.status} for row in rows])


@api_bp.route("/history/latest")
def latest_history():
    """Return the newest stored daily enrollment snapshot rows."""
    rows = DailyEnrollmentHistory.query.order_by(DailyEnrollmentHistory.snapshot_date.desc()).limit(500).all()
    return jsonify([
        {
            "course_id": row.course.course_id,
            "snapshot_date": row.snapshot_date.isoformat(),
            "learners_enrolled": row.learners_enrolled,
            "exam_registration": row.exam_registration,
            "google_members": row.google_members,
        }
        for row in rows
    ])
