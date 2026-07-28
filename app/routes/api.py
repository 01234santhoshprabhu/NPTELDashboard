from flask import Blueprint, jsonify, request, session

from app.extensions import db
from app.models import Course, DailyEnrollmentHistory, SchedulerLog, User, utcnow
from app.security import permission_required
from app.services.user_service import UserService


api_bp = Blueprint("api", __name__)


def course_payload(course):
    """Serialize a course for REST responses."""
    return {
        "course_id": course.course_id,
        "course_url": course.course_url,
        "title": course.title,
        "status": course.status,
        "department": course.department.name if course.department else None,
        "faculty": course.faculty.name if course.faculty else None,
    }


def history_payload(row):
    """Serialize a daily history row for REST responses."""
    return {
        "course_id": row.course.course_id,
        "snapshot_date": row.snapshot_date.isoformat(),
        "learners_enrolled": row.learners_enrolled,
        "exam_registration": row.exam_registration,
        "google_members": row.google_members,
        "raw_enrollment_status": row.raw_enrollment_status,
        "source": row.source,
    }


@api_bp.route("/auth/login", methods=["POST"])
def api_login():
    """Authenticate an API client using email and password."""
    payload = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=str(payload.get("email", "")).lower()).first()
    if not user or not user.is_active or not user.check_password(payload.get("password", "")):
        return jsonify({"error": "invalid_credentials"}), 401
    user.last_login_at = utcnow()
    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    permissions = sorted({permission.name for role in user.roles for permission in role.permissions})
    return jsonify({"user": {"email": user.email, "full_name": user.full_name}, "permissions": permissions})


@api_bp.route("/dashboard")
@permission_required("dashboard.view")
def dashboard_summary():
    """Return high-level dashboard metrics."""
    latest_date = db.session.query(db.func.max(DailyEnrollmentHistory.snapshot_date)).scalar()
    query = DailyEnrollmentHistory.query
    if latest_date:
        query = query.filter_by(snapshot_date=latest_date)
    rows = query.all()
    total_enrollment = sum(row.learners_enrolled or 0 for row in rows)
    total_exam = sum(row.exam_registration or 0 for row in rows)
    return jsonify(
        {
            "course_count": Course.query.count(),
            "history_rows": DailyEnrollmentHistory.query.count(),
            "latest_snapshot_date": latest_date.isoformat() if latest_date else None,
            "total_enrollment": total_enrollment,
            "total_exam_registration": total_exam,
            "error_count": sum(1 for row in rows if row.learners_enrolled is None),
        }
    )


@api_bp.route("/courses")
@permission_required("api.read")
def courses():
    """Return course catalog records for API clients."""
    limit = min(int(request.args.get("limit", 500)), 1000)
    rows = Course.query.order_by(Course.course_id.asc()).limit(limit).all()
    return jsonify([course_payload(row) for row in rows])


@api_bp.route("/courses/<course_id>/history")
@permission_required("api.read")
def course_history(course_id):
    """Return stored daily history for one course."""
    course = Course.query.filter_by(course_id=course_id).first_or_404()
    rows = course.daily_history.order_by(DailyEnrollmentHistory.snapshot_date.desc()).limit(366).all()
    return jsonify([history_payload(row) for row in rows])


@api_bp.route("/history/latest")
@permission_required("api.read")
def latest_history():
    """Return the newest stored daily enrollment snapshot rows."""
    latest_date = db.session.query(db.func.max(DailyEnrollmentHistory.snapshot_date)).scalar()
    query = DailyEnrollmentHistory.query
    if latest_date:
        query = query.filter_by(snapshot_date=latest_date)
    rows = query.order_by(DailyEnrollmentHistory.learners_enrolled.desc().nullslast()).limit(1000).all()
    return jsonify([history_payload(row) for row in rows])


@api_bp.route("/reports/daily")
@permission_required("reports.export")
def daily_report():
    """Return daily report metadata and totals."""
    latest_date = db.session.query(db.func.max(DailyEnrollmentHistory.snapshot_date)).scalar()
    rows = DailyEnrollmentHistory.query.filter_by(snapshot_date=latest_date).all() if latest_date else []
    return jsonify(
        {
            "snapshot_date": latest_date.isoformat() if latest_date else None,
            "row_count": len(rows),
            "total_enrollment": sum(row.learners_enrolled or 0 for row in rows),
            "total_exam_registration": sum(row.exam_registration or 0 for row in rows),
            "download": "/enrollment_report.csv",
        }
    )


@api_bp.route("/users", methods=["GET", "POST"])
@permission_required("users.manage")
def users():
    """List or create users through the REST API."""
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        user = UserService().create_user(
            email=payload["email"],
            full_name=payload["full_name"],
            password=payload["password"],
            role_names=payload.get("roles", []),
        )
        return jsonify({"id": user.id, "email": user.email}), 201
    rows = User.query.order_by(User.email.asc()).all()
    return jsonify([
        {"id": row.id, "email": row.email, "full_name": row.full_name, "roles": [role.name for role in row.roles], "is_active": row.is_active}
        for row in rows
    ])


@api_bp.route("/logs/scheduler")
@permission_required("scheduler.manage")
def scheduler_logs():
    """Return recent scheduler execution logs."""
    rows = SchedulerLog.query.order_by(SchedulerLog.started_at.desc()).limit(100).all()
    return jsonify([
        {
            "job_name": row.job_name,
            "status": row.status,
            "message": row.message,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }
        for row in rows
    ])
