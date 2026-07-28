# NPTEL Enrollment Dashboard

This project tracks course-wise NPTEL learner enrollment counts and publishes a GitHub Pages dashboard.

## Local Dashboard

Run:

```bash
python dashboard.py
```

Open:

```text
http://127.0.0.1:8765
```

The local dashboard refreshes the displayed data every 10 seconds. Use the **Regenerate now** button to run a fresh scrape.

## GitHub Pages Dashboard

The GitHub Pages dashboard lives in `docs/index.html`.

It reads:

- `docs/summary.json`
- `docs/enrollment_report.csv`

The page refreshes from `summary.json` every 10 seconds.

## Scheduled GitHub Update

The workflow `.github/workflows/update-enrollment.yml` refreshes dashboard data every 30 minutes and can also be run manually from the GitHub Actions tab.

## Important

Do not commit email passwords, app passwords, cookies, or `.env` files. Email credentials must be supplied through environment variables:

- `SENDER_EMAIL`
- `SENDER_PASSWORD`
- `RECEIVER_EMAIL`

## New Repository Auto Refresh

This repository includes `.github/workflows/update-enrollment.yml`, which refreshes enrollment and registration counts every 5 minutes on GitHub Actions and publishes `docs/` to the `gh-pages` branch.

For a new GitHub repository:

1. Push this project to the new repository.
2. In GitHub, open Settings > Pages.
3. Set source to the `gh-pages` branch.
4. Ensure Actions are enabled.
5. Run the `Update enrollment report` workflow manually once, or wait for the 5-minute schedule.

Local auto-refresh is separate from GitHub Actions. To run it locally:

```powershell
python manage.py start-5min-scheduler
```

Manual local refresh:

```powershell
python manage.py run-combined-refresh
```

