from app.config import Config
from app.services.refresh_service import DailyRefreshService


def run_daily_refresh(app, snapshot_date=None):
    """Execute one daily refresh inside the Flask application context."""
    with app.app_context():
        return DailyRefreshService().run(snapshot_date=snapshot_date)


def run_combined_refresh(app):
    """Refresh enrollment/register data and sync latest member files."""
    with app.app_context():
        service = DailyRefreshService()
        result = service.run()
        member_result = service.sync_member_files()
        return {"enrollment": result, "members": member_result}


def create_scheduler(app, every_5_minutes=False):
    """Create an APScheduler instance for daily or 5-minute refreshes."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError as exc:
        raise RuntimeError("APScheduler is required. Install requirements.txt first.") from exc

    scheduler = BackgroundScheduler(timezone=app.config.get("SCHEDULER_TIMEZONE", Config.SCHEDULER_TIMEZONE))
    if every_5_minutes:
        scheduler.add_job(
            func=lambda: run_combined_refresh(app),
            trigger="interval",
            minutes=5,
            id="five_minute_dashboard_refresh",
            name="Five minute dashboard refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=None,
        )
    else:
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


def start_scheduler(app, every_5_minutes=False):
    """Start and return the configured background scheduler."""
    scheduler = create_scheduler(app, every_5_minutes=every_5_minutes)
    scheduler.start()
    return scheduler
