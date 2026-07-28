from app.extensions import db
from app.models import Role, User


class UserService:
    """Application service for user management workflows."""

    def create_user(self, email, full_name, password, role_names=None, is_active=True):
        """Create a user with optional roles and commit the transaction."""
        normalized_email = email.lower().strip()
        if User.query.filter_by(email=normalized_email).first():
            raise ValueError("A user with this email already exists")
        user = User(email=normalized_email, full_name=full_name.strip(), is_active=is_active)
        user.set_password(password)
        if role_names:
            user.roles = Role.query.filter(Role.name.in_(role_names)).all()
        db.session.add(user)
        db.session.commit()
        return user

    def update_user_roles(self, user, role_names):
        """Replace a user's role assignments and commit the transaction."""
        user.roles = Role.query.filter(Role.name.in_(role_names or [])).all()
        db.session.commit()
        return user

    def set_active(self, user, is_active):
        """Enable or disable a user account and commit the transaction."""
        user.is_active = bool(is_active)
        db.session.commit()
        return user

    def delete_user(self, user):
        """Delete a user account and commit the transaction."""
        db.session.delete(user)
        db.session.commit()
