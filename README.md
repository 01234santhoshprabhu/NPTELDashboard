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

