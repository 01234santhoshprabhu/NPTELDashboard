import subprocess
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_URL = "https://github.com/01234santhoshprabhu/count.git"
PUBLISH_DIR = BASE_DIR / ".publish-gh-pages"
LOCK_FILE = BASE_DIR / "auto_publish_dashboard.lock"
LOG_FILE = Path(
    __import__("os").environ.get(
        "AUTO_PUBLISH_LOG",
        str(BASE_DIR / "auto_publish_dashboard.log"),
    )
)


def log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except PermissionError:
        print("[log file is locked; continuing without writing this line]", flush=True)


def run(command, cwd):
    log(f"Running: {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout.strip():
        log(completed.stdout.strip())
    return completed.returncode


def acquire_lock():
    if LOCK_FILE.exists():
        try:
            age_seconds = time.time() - LOCK_FILE.stat().st_mtime
            if age_seconds < 900:
                log("Another publish cycle appears to be running; skipping this cycle.")
                return False
            log("Removing stale publish lock.")
            LOCK_FILE.unlink()
        except OSError:
            log("Publish lock is busy; skipping this cycle.")
            return False

    try:
        LOCK_FILE.write_text(str(datetime.now()), encoding="utf-8")
        return True
    except OSError as exc:
        log(f"Could not create publish lock: {exc}")
        return False


def release_lock():
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def copy_dashboard_files(target_dir):
    for filename in ["index.html", "summary.json", "enrollment_report.csv"]:
        source = BASE_DIR / "docs" / filename
        target = target_dir / filename
        target.write_bytes(source.read_bytes())


def publish_live_branch():
    if PUBLISH_DIR.exists():
        shutil.rmtree(PUBLISH_DIR, ignore_errors=True)

    code = run(["git", "clone", "--depth", "1", "--branch", "gh-pages", REPO_URL, str(PUBLISH_DIR)], BASE_DIR)
    if code != 0:
        log("Could not clone gh-pages branch; skipping publish.")
        return

    copy_dashboard_files(PUBLISH_DIR)
    run(["git", "config", "user.name", "NPTEL Automation"], PUBLISH_DIR)
    run(["git", "config", "user.email", "nptel@example.com"], PUBLISH_DIR)
    run(["git", "add", "index.html", "summary.json", "enrollment_report.csv"], PUBLISH_DIR)
    code = run(["git", "commit", "-m", "Auto refresh live dashboard data"], PUBLISH_DIR)
    if code == 0:
        run(["git", "push", "origin", "gh-pages"], PUBLISH_DIR)
    else:
        log("No live data change to commit.")

    shutil.rmtree(PUBLISH_DIR, ignore_errors=True)


def publish_once():
    if not acquire_lock():
        return

    try:
        publish_once_locked()
    finally:
        release_lock()


def publish_once_locked():
    code = run([sys.executable, "update_github_report.py"], BASE_DIR)
    if code != 0:
        log("Report update failed; skipping publish.")
        return

    publish_live_branch()


def main():
    interval_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    log(f"Auto publisher started. Interval: {interval_seconds} seconds.")
    while True:
        started = time.time()
        try:
            publish_once()
        except Exception as exc:
            log(f"Auto publish error: {exc}")
        elapsed = time.time() - started
        sleep_for = max(10, interval_seconds - elapsed)
        log(f"Sleeping for {int(sleep_for)} seconds.")
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
