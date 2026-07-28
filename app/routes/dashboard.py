from flask import Blueprint, jsonify

from app.models import Course, DailyEnrollmentHistory


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/enterprise")
def index():
    """Return a simple enterprise dashboard status payload."""
    return jsonify(
        {
            "name": "NPTEL Enterprise Course Intelligence Platform",
            "courses": Course.query.count(),
            "history_rows": DailyEnrollmentHistory.query.count(),
        }
    )
