import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
MAIN_EXCEL = BASE_DIR / "enrollment_data.xlsx"
UPDATED_EXCEL = BASE_DIR / "enrollment_data_updated.xlsx"
CSV_REPORT = BASE_DIR / "enrollment_report.csv"
ENROLL_SCRIPT = BASE_DIR / "ENROLL.py"
RUN_LOG = BASE_DIR / "dashboard_run.log"

job_lock = threading.Lock()
job_state = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "return_code": None,
    "message": "Ready",
}


def latest_excel_file():
    candidates = [p for p in [MAIN_EXCEL, UPDATED_EXCEL] if p.exists()]
    if not candidates:
        return MAIN_EXCEL
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_tail(path, max_chars=6000):
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def rebuild_csv(df):
    vals = pd.to_numeric(df["Learners_Enrolled"], errors="coerce")
    total = int(vals.fillna(0).sum())
    csv_df = df[["Course_ID", "Learners_Enrolled"]].copy()
    total_row = pd.DataFrame([["TOTAL", total]], columns=["Course_ID", "Learners_Enrolled"])
    csv_df = pd.concat([csv_df, total_row], ignore_index=True)
    csv_df.to_csv(CSV_REPORT, index=False)


def build_stats():
    source = latest_excel_file()
    if not source.exists():
        return {
            "ok": False,
            "message": "No enrollment Excel output found yet.",
            "source": str(source),
        }

    df = pd.read_excel(source)
    if "Course_ID" not in df.columns and "Course_URL" in df.columns:
        df["Course_ID"] = df["Course_URL"].astype(str).str.rstrip("/").str.split("/").str[-1]

    vals = pd.to_numeric(df["Learners_Enrolled"], errors="coerce")
    error_df = df[vals.isna()].copy()
    numeric_df = df[vals.notna()].copy()
    numeric_df["_count"] = vals[vals.notna()].astype(int)
    top_df = numeric_df.sort_values("_count", ascending=False).head(10)

    return {
        "ok": True,
        "source_file": source.name,
        "source_mtime": datetime.fromtimestamp(source.stat().st_mtime).strftime("%d %b %Y, %I:%M:%S %p"),
        "course_count": int(len(df)),
        "numeric_count": int(vals.notna().sum()),
        "error_count": int(vals.isna().sum()),
        "total_enrollment": int(vals.fillna(0).sum()),
        "max_count": int(vals.max()) if vals.notna().any() else 0,
        "min_count": int(vals.min()) if vals.notna().any() else 0,
        "top_courses": [
            {"course_id": str(row["Course_ID"]), "count": int(row["_count"])}
            for _, row in top_df.iterrows()
        ],
        "errors": [
            {
                "course_id": str(row.get("Course_ID", "")),
                "course_url": str(row.get("Course_URL", "")),
                "status": str(row.get("Learners_Enrolled", "")),
            }
            for _, row in error_df.head(20).iterrows()
        ],
        "report_file": CSV_REPORT.name,
    }


def run_regenerate():
    with job_lock:
        job_state.update(
            {
                "running": True,
                "started_at": datetime.now().strftime("%d %b %Y, %I:%M:%S %p"),
                "finished_at": None,
                "return_code": None,
                "message": "Regenerating enrollment data...",
            }
        )

    env = os.environ.copy()
    env.pop("USE_SAVED_COUNTS", None)
    env.pop("BROWSER_RECHECK", None)

    with RUN_LOG.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            [sys.executable, str(ENROLL_SCRIPT)],
            cwd=str(BASE_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
        )
        return_code = process.wait()

    message = "Regeneration complete" if return_code == 0 else "Regeneration failed"
    try:
        source = latest_excel_file()
        if source.exists():
            df = pd.read_excel(source)
            rebuild_csv(df)
            message += f"; report refreshed from {source.name}"
    except Exception as exc:
        message += f"; report refresh failed: {exc}"

    with job_lock:
        job_state.update(
            {
                "running": False,
                "finished_at": datetime.now().strftime("%d %b %Y, %I:%M:%S %p"),
                "return_code": return_code,
                "message": message,
            }
        )


def start_regenerate():
    with job_lock:
        if job_state["running"]:
            return False
        thread = threading.Thread(target=run_regenerate, daemon=True)
        thread.start()
        return True


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NPTEL Enrollment Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d9dee8;
      --blue: #1f5fa8;
      --green: #1c7c54;
      --amber: #9a6700;
      --red: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", Arial, sans-serif;
      letter-spacing: 0;
    }
    header {
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 18px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }
    h1 { margin: 0; font-size: 24px; line-height: 1.2; }
    .sub { color: var(--muted); margin-top: 4px; font-size: 13px; }
    main { max-width: 1180px; margin: 0 auto; padding: 22px; }
    .toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    button {
      border: 1px solid #174f8a;
      background: var(--blue);
      color: #fff;
      padding: 10px 14px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
    }
    button:disabled { opacity: .6; cursor: wait; }
    .status {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--muted);
      padding: 9px 11px;
      border-radius: 6px;
      font-size: 13px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .metric, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .metric .label { color: var(--muted); font-size: 13px; }
    .metric .value { font-size: 30px; font-weight: 700; margin-top: 8px; }
    .metric.good .value { color: var(--green); }
    .metric.warn .value { color: var(--amber); }
    .metric.bad .value { color: var(--red); }
    .wide {
      display: grid;
      grid-template-columns: 1.35fr .9fr;
      gap: 14px;
    }
    .panel h2 { margin: 0 0 12px; font-size: 17px; color: #23456f; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { border-bottom: 1px solid #eef1f5; padding: 9px 8px; text-align: left; }
    th { color: var(--muted); font-weight: 600; background: #f5f7fa; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px 18px;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 16px;
    }
    .meta b { color: var(--ink); }
    pre {
      white-space: pre-wrap;
      max-height: 260px;
      overflow: auto;
      background: #111827;
      color: #e5e7eb;
      padding: 12px;
      border-radius: 6px;
      font-size: 12px;
    }
    .empty { color: var(--muted); padding: 10px 0; }
    @media (max-width: 900px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .wide { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      main { padding: 14px; }
      .grid { grid-template-columns: 1fr; }
      .meta { grid-template-columns: 1fr; }
      h1 { font-size: 20px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>NPTEL Enrollment Dashboard</h1>
      <div class="sub">Stats refresh every 10 seconds. Full regeneration runs only when requested.</div>
    </div>
    <div class="toolbar">
      <button id="regenBtn" type="button">Regenerate now</button>
      <div class="status" id="jobStatus">Ready</div>
    </div>
  </header>
  <main>
    <section class="meta" id="meta"></section>
    <section class="grid">
      <div class="metric"><div class="label">Courses</div><div class="value" id="courses">-</div></div>
      <div class="metric good"><div class="label">Numeric Counts</div><div class="value" id="numeric">-</div></div>
      <div class="metric warn"><div class="label">Missing/Error</div><div class="value" id="errors">-</div></div>
      <div class="metric"><div class="label">Total Enrollment</div><div class="value" id="total">-</div></div>
    </section>
    <section class="wide">
      <div class="panel">
        <h2>Top Courses</h2>
        <table>
          <thead><tr><th>Course ID</th><th class="num">Learners</th></tr></thead>
          <tbody id="topRows"></tbody>
        </table>
      </div>
      <div class="panel">
        <h2>Missing Courses</h2>
        <div id="errorRows"></div>
      </div>
    </section>
    <section class="panel" style="margin-top:14px;">
      <h2>Latest Run Log</h2>
      <pre id="logBox">No run log yet.</pre>
    </section>
  </main>
  <script>
    const fmt = new Intl.NumberFormat("en-IN");
    async function getJson(url, options) {
      const response = await fetch(url, options);
      return response.json();
    }
    function text(value) {
      return value === undefined || value === null ? "" : String(value);
    }
    async function refreshStats() {
      const data = await getJson("/api/stats");
      if (!data.ok) {
        document.getElementById("jobStatus").textContent = data.message || "No data";
        return;
      }
      document.getElementById("courses").textContent = fmt.format(data.course_count);
      document.getElementById("numeric").textContent = fmt.format(data.numeric_count);
      document.getElementById("errors").textContent = fmt.format(data.error_count);
      document.getElementById("total").textContent = fmt.format(data.total_enrollment);
      document.getElementById("meta").innerHTML = `
        <div>Source file: <b>${text(data.source_file)}</b></div>
        <div>Last file update: <b>${text(data.source_mtime)}</b></div>
        <div>CSV report: <b>${text(data.report_file)}</b></div>
        <div>Min / max count: <b>${fmt.format(data.min_count)} / ${fmt.format(data.max_count)}</b></div>
      `;
      document.getElementById("topRows").innerHTML = data.top_courses.map(row => `
        <tr><td>${text(row.course_id)}</td><td class="num">${fmt.format(row.count)}</td></tr>
      `).join("");
      document.getElementById("errorRows").innerHTML = data.errors.length
        ? `<table><thead><tr><th>Course ID</th><th>Status</th></tr></thead><tbody>${data.errors.map(row => `
            <tr><td>${text(row.course_id)}</td><td>${text(row.status)}</td></tr>
          `).join("")}</tbody></table>`
        : `<div class="empty">No missing courses.</div>`;
    }
    async function refreshJob() {
      const data = await getJson("/api/job");
      document.getElementById("jobStatus").textContent = data.message || "Ready";
      document.getElementById("regenBtn").disabled = !!data.running;
      document.getElementById("logBox").textContent = data.log || "No run log yet.";
    }
    async function refreshAll() {
      await Promise.all([refreshStats(), refreshJob()]);
    }
    document.getElementById("regenBtn").addEventListener("click", async () => {
      await getJson("/api/regenerate", { method: "POST" });
      await refreshAll();
    });
    refreshAll();
    setInterval(refreshAll, 10000);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/stats":
            try:
                self.send_json(build_stats())
            except Exception as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=500)
        elif path == "/api/job":
            with job_lock:
                payload = dict(job_state)
            payload["log"] = read_tail(RUN_LOG)
            self.send_json(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/regenerate":
            started = start_regenerate()
            self.send_json({"started": started, "running": True if started else job_state["running"]})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"NPTEL dashboard running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
