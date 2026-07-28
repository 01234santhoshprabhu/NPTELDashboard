import argparse
from datetime import date
from pathlib import Path

from app import create_app
from app.config import Config
from app.database import init_database
from app.scheduler import run_daily_refresh, start_scheduler
from app.services.enrollment_service import EnrollmentImportService


app = create_app()


def main():
    """Run database and import management commands."""
    parser = argparse.ArgumentParser(description="NECIP management commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db")
    subparsers.add_parser("run-daily-refresh")
    subparsers.add_parser("start-scheduler")
    import_parser = subparsers.add_parser("import-enrollment")
    import_parser.add_argument("--report", default=str(Path("docs") / "enrollment_report.csv"))
    import_parser.add_argument("--date", default=None)
    args = parser.parse_args()

    with app.app_context():
        if args.command == "init-db":
            init_database(Config.ADMIN_EMAIL, Config.ADMIN_PASSWORD)
            print("Database initialized")
        elif args.command == "import-enrollment":
            snapshot = date.fromisoformat(args.date) if args.date else None
            result = EnrollmentImportService().import_report(args.report, snapshot_date=snapshot)
            print(result)
        elif args.command == "run-daily-refresh":
            print(run_daily_refresh(app))
        elif args.command == "start-scheduler":
            scheduler = start_scheduler(app)
            print("Scheduler started. Press Ctrl+C to stop.")
            try:
                import time
                while True:
                    time.sleep(60)
            finally:
                scheduler.shutdown()


if __name__ == "__main__":
    main()

