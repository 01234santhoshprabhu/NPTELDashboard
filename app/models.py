from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)


def utcnow():
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Role(db.Model):
    """A named access role assigned to one or more users."""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    permissions = db.relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(db.Model):
    """A granular capability used by role based access checks."""

    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False, default="")
    roles = db.relationship("Role", secondary=role_permissions, back_populates="permissions")


class User(db.Model):
    """Application user with password credentials and assigned roles."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    roles = db.relationship("Role", secondary=user_roles, backref=db.backref("users", lazy="dynamic"))

    def set_password(self, password):
        """Hash and store a plaintext password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True when the plaintext password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission_name):
        """Return True when any assigned role grants the requested permission."""
        return any(permission.name == permission_name for role in self.roles for permission in role.permissions)


class Department(db.Model):
    """Academic department that owns courses and faculty."""

    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    code = db.Column(db.String(30), unique=True, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class Faculty(db.Model):
    """Faculty member associated with one or more courses."""

    __tablename__ = "faculty"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    department = db.relationship("Department", backref="faculty_members")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class Course(db.Model):
    """NPTEL course identity and catalog metadata."""

    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.String(80), unique=True, nullable=False, index=True)
    course_url = db.Column(db.String(500), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(60), nullable=False, default="active")
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)
    department = db.relationship("Department", backref="courses")
    faculty = db.relationship("Faculty", backref="courses")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class DailyEnrollmentHistory(db.Model):
    """Daily enrollment, exam registration, and member count snapshot for a course."""

    __tablename__ = "daily_enrollment_history"
    __table_args__ = (db.UniqueConstraint("course_id", "snapshot_date", name="uq_course_snapshot_date"),)

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)
    learners_enrolled = db.Column(db.Integer, nullable=True)
    exam_registration = db.Column(db.Integer, nullable=True)
    google_members = db.Column(db.Integer, nullable=True)
    raw_enrollment_status = db.Column(db.String(255), nullable=True)
    raw_exam_status = db.Column(db.String(255), nullable=True)
    source = db.Column(db.String(120), nullable=False, default="csv_import")
    captured_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    course = db.relationship("Course", backref=db.backref("daily_history", lazy="dynamic"))


class SchedulerLog(db.Model):
    """Execution log for automated refresh jobs."""

    __tablename__ = "scheduler_logs"

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(120), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False)
    message = db.Column(db.Text, nullable=False, default="")
    started_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)


class AuditLog(db.Model):
    """Security and administration audit event."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(120), nullable=False, default="system")
    entity_id = db.Column(db.String(120), nullable=True)
    details = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    actor = db.relationship("User")


class ApiToken(db.Model):
    """Hashed API token metadata for REST integrations."""

    __tablename__ = "api_tokens"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
