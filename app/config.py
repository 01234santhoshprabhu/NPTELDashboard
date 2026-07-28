import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Application configuration loaded from environment variables."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'necip.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
    }
    SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata")
    DAILY_REFRESH_HOUR = int(os.getenv("DAILY_REFRESH_HOUR", "9"))
    DAILY_REFRESH_MINUTE = int(os.getenv("DAILY_REFRESH_MINUTE", "0"))
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@nptel.local")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
    PUBLIC_DASHBOARD_BASE_URL = os.getenv(
        "PUBLIC_DASHBOARD_BASE_URL",
        "https://01234santhoshprabhu.github.io/NPTELDashboard/",
    ).rstrip("/")
    USE_REMOTE_DASHBOARD_ASSETS = os.getenv(
        "USE_REMOTE_DASHBOARD_ASSETS", "0"
    ).lower() in {"1", "true", "yes", "on"}
