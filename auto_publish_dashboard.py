import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
GH_PAGES_DIR = BASE_DIR.parent / "count-gh-pages"
LOG_FILE = BASE_DIR / "auto_publish_dashboard.log"


def log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


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


def publish_once():
    code = run([sys.executable, "update_github_report.py"], BASE_DIR)
    if code != 0:
        log("Report update failed; skipping publish.")
        return

    run(["git", "pull", "--rebase", "origin", "main"], BASE_DIR)
    run(["git", "add", "docs/summary.json", "docs/enrollment_report.csv"], BASE_DIR)
    code = run(["git", "commit", "-m", "Auto refresh enrollment dashboard data"], BASE_DIR)
    if code == 0:
        run(["git", "push"], BASE_DIR)
    else:
        log("No main-branch data change to commit.")

    if not GH_PAGES_DIR.exists():
        run(["git", "worktree", "add", str(GH_PAGES_DIR), "gh-pages"], BASE_DIR)

    run(["git", "pull", "--rebase", "origin", "gh-pages"], GH_PAGES_DIR)
    for filename in ["index.html", "summary.json", "enrollment_report.csv"]:
        source = BASE_DIR / "docs" / filename
        target = GH_PAGES_DIR / filename
        target.write_bytes(source.read_bytes())

    run(["git", "add", "index.html", "summary.json", "enrollment_report.csv"], GH_PAGES_DIR)
    code = run(["git", "commit", "-m", "Auto refresh live dashboard data"], GH_PAGES_DIR)
    if code == 0:
        run(["git", "push"], GH_PAGES_DIR)
    else:
        log("No live-branch data change to commit.")


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
