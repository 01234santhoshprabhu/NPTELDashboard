from datetime import date

from app.extensions import db
from app.models import Course, DailyEnrollmentHistory, Role, User


class CourseRepository:
    """Database access layer for course entities."""

    def get_or_create(self, course_id, course_url=None):
        """Fetch a course by code or create it when it does not exist."""
        course = Course.query.filter_by(course_id=course_id).first()
        if course is None:
            course = Course(course_id=course_id, course_url=course_url)
            db.session.add(course)
        elif course_url and not course.course_url:
            course.course_url = course_url
        return course


class EnrollmentHistoryRepository:
    """Database access layer for daily enrollment snapshots."""

    def upsert_daily_snapshot(self, course, snapshot_date, learners, exam_registration, members, raw_enrollment, raw_exam, source):
        """Insert or update one course snapshot for a date."""
        history = DailyEnrollmentHistory.query.filter_by(course_id=course.id, snapshot_date=snapshot_date).first()
        if history is None:
            history = DailyEnrollmentHistory(course=course, snapshot_date=snapshot_date)
            db.session.add(history)
        history.learners_enrolled = learners
        history.exam_registration = exam_registration
        history.google_members = members
        history.raw_enrollment_status = raw_enrollment
        history.raw_exam_status = raw_exam
        history.source = source
        return history

    def latest_snapshot_date(self):
        """Return the most recent snapshot date stored in history."""
        return db.session.query(db.func.max(DailyEnrollmentHistory.snapshot_date)).scalar() or date.today()


class UserRepository:
    """Database access layer for users and roles."""

    def find_by_email(self, email):
        """Return a user by email address."""
        return User.query.filter_by(email=email.lower()).first()

    def get_role(self, name):
        """Return a role by role name."""
        return Role.query.filter_by(name=name).first()
