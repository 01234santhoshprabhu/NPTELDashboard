from app.config import Config
from app.services.refresh_service import DailyRefreshService


def run_daily_refresh(app, snapshot_date=None):
    """Execute one daily refresh inside the Flask application context."""
    with app.app_context():
        return DailyRefreshService().run(snapshot_date=snapshot_date)


def create_scheduler(app):
    """Create an APScheduler instance configured for the 9:00 AM IST refresh."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError as exc:
        raise RuntimeError("APScheduler is required. Install requirements.txt first.") from exc

    scheduler = BackgroundScheduler(timezone=app.config.get("SCHEDULER_TIMEZONE", Config.SCHEDULER_TIMEZONE))
    scheduler.add_job(
        func=lambda: run_daily_refresh(app),
        trigger="cron",
        hour=app.config.get("DAILY_REFRESH_HOUR", Config.DAILY_REFRESH_HOUR),
        minute=app.config.get("DAILY_REFRESH_MINUTE", Config.DAILY_REFRESH_MINUTE),
        id="daily_enrollment_refresh",
        name="Daily enrollment refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def start_scheduler(app):
    """Start and return the configured background scheduler."""
    scheduler = create_scheduler(app)
    scheduler.start()
    return scheduler
