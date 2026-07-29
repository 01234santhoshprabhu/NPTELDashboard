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


## Public Login App on Render Free

Recommended free public host: Render Free Web Service with Render Free PostgreSQL.

Live static dashboard:

```text
https://01234santhoshprabhu.github.io/NPTELDashboard/
```

Repository:

```text
https://github.com/01234santhoshprabhu/NPTELDashboard
```

To deploy the login/admin Flask application publicly:

1. Open Render and choose New > Blueprint.
2. Connect the GitHub repository `01234santhoshprabhu/NPTELDashboard`.
3. Select this repository root. Render reads `render.yaml` automatically.
4. After deploy, open the Render web service URL and go to `/login`.
5. Change `ADMIN_EMAIL` and `ADMIN_PASSWORD` in Render environment variables before sharing the app.

The deployed Flask app uses:

- `DATABASE_URL`: Render PostgreSQL connection string.
- `PUBLIC_DASHBOARD_BASE_URL`: `https://01234santhoshprabhu.github.io/NPTELDashboard/`.
- `USE_REMOTE_DASHBOARD_ASSETS=true`: after login, dashboard JSON and CSV are proxied from the live GitHub Pages output, so counts follow the 5-minute GitHub Actions refresh.

Database location:

- Local development: `instance/necip.db` SQLite file.
- Render deployment: Render Dashboard > PostgreSQL > `nptel-dashboard-db`.

User management:

- Login as an admin.
- Open `/admin/users`.
- Add email IDs as `admin`, `operator`, or `viewer`.
- Remove an existing user with the delete action on the same page.
- Use `admin` only for trusted users because admins can manage other users.

Useful URLs after deploy:

- `/login`: login page.
- `/enterprise`: authenticated count dashboard.
- `/admin/`: admin dashboard.
- `/admin/tools`: refresh/import/export tools.
- `/admin/users`: user management.
- `/api/v1/dashboard`: dashboard REST API.
- `/logout`: logout.

Render Free notes:

- The free web service can sleep after idle time, so first load may be slow.
- Render free PostgreSQL is suitable for testing/demo use, not long-term production data retention.

## Admin Tool: Import CSV + Update Drive

The `/admin/tools` page includes **Import CSV + Update Drive**.

It does three things:

1. Imports `docs/enrollment_report.csv` into PostgreSQL.
2. Rebuilds `docs/summary.json` from that CSV.
3. Publishes dashboard files back to GitHub when `GITHUB_PUBLISH_TOKEN` is configured in Render.

Required Render environment variable for publishing:

```text
GITHUB_PUBLISH_TOKEN=<GitHub fine-grained token with contents read/write access to 01234santhoshprabhu/NPTELDashboard>
```

Optional environment variables:

```text
GITHUB_REPOSITORY=01234santhoshprabhu/NPTELDashboard
GITHUB_PUBLISH_BRANCH=main
```

Without `GITHUB_PUBLISH_TOKEN`, the tool still imports CSV data into the database and rebuilds the local summary, then shows a clear warning that GitHub publishing is not configured.
