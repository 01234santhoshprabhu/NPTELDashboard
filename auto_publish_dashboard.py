import subprocess
import sys
import time
import shutil
import os
import tempfile
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_URL = "https://github.com/01234santhoshprabhu/count.git"
LOCK_FILE = BASE_DIR / "auto_publish_dashboard.lock"
MEMBER_OUTPUT_DIR = Path.home() / "Documents" / "Enrollment script" / "member_test" / "output"
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


def sync_member_files():
    member_files = {
        "summary_test.json": "member_summary.json",
        "member_counts_test.csv": "member_counts.csv",
    }
    for source_name, target_name in member_files.items():
        source = MEMBER_OUTPUT_DIR / source_name
        target = BASE_DIR / "docs" / target_name
        if source.exists():
            target.write_bytes(source.read_bytes())
        else:
            log(f"Member test file missing, skipping: {source}")


def copy_dashboard_files(target_dir):
    for filename in [
        "index.html",
        "summary.json",
        "enrollment_report.csv",
        "member_summary.json",
        "member_counts.csv",
    ]:
        source = BASE_DIR / "docs" / filename
        target = target_dir / filename
        if source.exists():
            target.write_bytes(source.read_bytes())


def remove_publish_dir(path):
    shutil.rmtree(path, ignore_errors=True)


def cleanup_old_publish_dirs(current_dir=None):
    for path in BASE_DIR.glob(".publish-gh-pages-*"):
        if current_dir is not None and path == current_dir:
            continue
        remove_publish_dir(path)


def publish_live_branch():
    publish_dir = Path(
        tempfile.mkdtemp(
            prefix=f"nptel-gh-pages-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.getpid()}-"
        )
    )

    try:
        code = run(["git", "clone", "--depth", "1", "--branch", "gh-pages", REPO_URL, str(publish_dir)], BASE_DIR)
        if code != 0:
            log("Could not clone gh-pages branch; skipping publish.")
            return

        copy_dashboard_files(publish_dir)
        run(["git", "config", "user.name", "NPTEL Automation"], publish_dir)
        run(["git", "config", "user.email", "nptel@example.com"], publish_dir)
        run([
            "git",
            "add",
            "index.html",
            "summary.json",
            "enrollment_report.csv",
            "member_summary.json",
            "member_counts.csv",
        ], publish_dir)
        code = run(["git", "commit", "-m", "Auto refresh live dashboard data"], publish_dir)
        if code == 0:
            run(["git", "push", "origin", "gh-pages"], publish_dir)
        else:
            log("No live data change to commit.")
    finally:
        remove_publish_dir(publish_dir)


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
    sync_member_files()

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
