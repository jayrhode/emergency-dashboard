"""
generate_dashboard.py — Build emergency_dashboard.html from Supabase data.

Usage:  python generate_dashboard.py
Reads:  .env.local for SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
Output: emergency_dashboard.html in the project root
"""

import os, html
from datetime import date, datetime
from pathlib import Path
from collections import OrderedDict
from dotenv import load_dotenv
from supabase import create_client

# ── Config ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent          # emergency-dashboard/
OUTPUT_FILE = PROJECT_DIR / "emergency_dashboard.html"
INDEX_FILE = PROJECT_DIR / "index.html"

load_dotenv(PROJECT_DIR / ".env.local")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Estimator colors — consistent palette
ESTIMATOR_COLORS = {}
COLOR_PALETTE = [
    "#2563EB", "#7C3AED", "#059669", "#D97706",
    "#DC2626", "#0891B2", "#9333EA", "#CA8A04",
]


def get_color(estimator: str) -> str:
    if estimator not in ESTIMATOR_COLORS:
        idx = len(ESTIMATOR_COLORS) % len(COLOR_PALETTE)
        ESTIMATOR_COLORS[estimator] = COLOR_PALETTE[idx]
    return ESTIMATOR_COLORS[estimator]


def initials(name: str) -> str:
    parts = name.replace("-", " ").split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


def anchor_id(name: str) -> str:
    return name.replace(" ", "_").replace("-", "_")


def age_class(days: int) -> str:
    if days >= 60:
        return "age-critical"
    if days >= 30:
        return "age-warning"
    return "age-ok"


def esc(text: str) -> str:
    return html.escape(str(text)) if text else ""


def format_report_date(d: str) -> str:
    """'2026-03-31' -> 'March 31, 2026'"""
    dt = datetime.strptime(d, "%Y-%m-%d")
    return dt.strftime("%B %d, %Y").replace(" 0", " ")


def build_html(active_jobs: list, snapshot: dict, new_job_numbers: list, report_date: str):
    """Generate the full dashboard HTML."""
    # Group by estimator, sorted alphabetically
    by_est = OrderedDict()
    for job in sorted(active_jobs, key=lambda j: (j["estimator"], -j["days_open"])):
        est = job["estimator"]
        by_est.setdefault(est, []).append(job)

    total_active = snapshot.get("total_active", len(active_jobs))
    new_count = snapshot.get("new_count", 0)
    closed_count = snapshot.get("closed_count", 0)

    # Total unique jobs this month
    month_prefix = report_date[:7]  # "2026-03"
    total_month = len(set(j["job_number"] for j in active_jobs
                         if j.get("date_received", "").startswith(month_prefix))
                      | set(j["job_number"] for j in active_jobs))
    # Actually pull from DB — count all jobs first_seen this month
    # For now use the count of all known jobs (active + closed this month)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    pretty_date = format_report_date(report_date)

    # ── Sidebar nav ──
    sidebar_pills = []
    for est, jobs in by_est.items():
        c = get_color(est)
        aid = anchor_id(est)
        ini = initials(est)
        n = len(jobs)
        sidebar_pills.append(
            f'    <a href="#{aid}" class="nav-pill" style="--pill-color:{c};">\n'
            f'      <span class="nav-init">{ini}</span>\n'
            f'      <span class="nav-name">{esc(est)}</span>\n'
            f'      <span class="nav-ct">{n}</span>\n'
            f'    </a>'
        )

    # ── Estimator cards ──
    cards = []
    for est, jobs in by_est.items():
        c = get_color(est)
        aid = anchor_id(est)
        ini = initials(est)
        n = len(jobs)
        job_word = "job" if n == 1 else "jobs"

        rows = []
        for j in jobs:
            is_new = j["job_number"] in new_job_numbers
            row_cls = ' class="row-new"' if is_new else ""
            new_badge = '<span class="badge-new">NEW</span>' if is_new else ""
            ac = age_class(j["days_open"])
            rows.append(
                f'            <tr{row_cls}>\n'
                f'              <td class="td-job">{esc(j["job_number"])}{new_badge}</td>\n'
                f'              <td>{esc(j["customer"])}</td>\n'
                f'              <td class="td-loc">{esc(j["address"])}, {esc(j["city"])}</td>\n'
                f'              <td class="td-desc">{esc(j["description"])}</td>\n'
                f'              <td class="td-days {ac}">{j["days_open"]}d</td>\n'
                f'            </tr>'
            )

        cards.append(
            f'    <!-- {esc(est)} — {n} {job_word} -->\n'
            f'    <section class="est-card" id="{aid}">\n'
            f'      <div class="card-hdr" style="--cc:{c};">\n'
            f'        <div class="avatar">{ini}</div>\n'
            f'        <div>\n'
            f'          <div class="card-name">{esc(est)}</div>\n'
            f'          <div class="card-sub">{n} active {job_word}</div>\n'
            f'        </div>\n'
            f'      </div>\n'
            f'      <div class="tbl-wrap">\n'
            f'        <table>\n'
            f'          <thead><tr>\n'
            f'            <th>Job #</th><th>Customer</th><th>Location</th>\n'
            f'            <th>Description</th><th>Age</th>\n'
            f'          </tr></thead>\n'
            f'          <tbody>\n'
            + "\n".join(rows) + "\n"
            f'          </tbody>\n'
            f'        </table>\n'
            f'      </div>\n'
            f'    </section>'
        )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Winmar Emergency Dashboard — {pretty_date}</title>
<style>
  :root{{
    --bg:#0f172a;--surf:#1e293b;--surf2:#263346;--bdr:#334155;
    --tx:#f1f5f9;--muted:#94a3b8;
    --green:#22c55e;--green-bg:rgba(34,197,94,.1);
    --blue:#3b82f6;--purple:#a855f7;--orange:#f97316;
    --amber:#f59e0b;--red:#ef4444;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:var(--bg);color:var(--tx);min-height:100vh}}

  /* ── Password Gate ── */
  #gate{{position:fixed;inset:0;background:var(--bg);z-index:9999;
        display:flex;align-items:center;justify-content:center}}
  .gate-box{{background:var(--surf);border:1px solid var(--bdr);border-radius:16px;
             padding:40px 48px;width:100%;max-width:380px;text-align:center}}
  .gate-logo{{font-size:20px;font-weight:700;margin-bottom:6px}}
  .gate-logo em{{color:var(--orange);font-style:normal}}
  .gate-sub{{font-size:13px;color:var(--muted);margin-bottom:28px}}
  .gate-box input{{width:100%;background:var(--bg);border:1px solid var(--bdr);
                   border-radius:8px;padding:10px 14px;color:var(--tx);
                   font-size:15px;outline:none;margin-bottom:12px}}
  .gate-box input:focus{{border-color:var(--orange)}}
  .gate-box button{{width:100%;background:var(--orange);border:none;border-radius:8px;
                    padding:10px;color:#fff;font-size:15px;font-weight:600;cursor:pointer}}
  .gate-box button:hover{{opacity:.9}}
  .gate-err{{color:var(--red);font-size:13px;margin-top:8px;display:none}}

  /* ── Topbar ── */
  .topbar{{background:var(--surf);border-bottom:1px solid var(--bdr);
           padding:14px 32px;display:flex;align-items:center;gap:12px;
           position:sticky;top:0;z-index:100;box-shadow:0 1px 8px rgba(0,0,0,.3)}}
  .logo{{font-size:19px;font-weight:700;letter-spacing:-.5px}}
  .logo em{{color:var(--orange);font-style:normal}}
  .report-meta{{margin-left:auto;font-size:12px;color:var(--muted);text-align:right;line-height:1.5}}

  /* ── KPI strip ── */
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;
         padding:24px 32px;max-width:1500px;margin:0 auto}}
  .kpi{{background:var(--surf);border:1px solid var(--bdr);border-radius:12px;
        padding:20px 24px;position:relative;overflow:hidden}}
  .kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
  .kpi.k-new::before    {{background:var(--green)}}
  .kpi.k-progress::before{{background:var(--orange)}}
  .kpi.k-month::before  {{background:var(--blue)}}
  .kpi.k-closed::before {{background:var(--purple)}}
  .kpi-lbl{{font-size:11px;font-weight:600;text-transform:uppercase;
             letter-spacing:.8px;color:var(--muted);margin-bottom:8px}}
  .kpi-num{{font-size:52px;font-weight:800;line-height:1;letter-spacing:-2px}}
  .k-new .kpi-num      {{color:var(--green)}}
  .k-progress .kpi-num {{color:var(--orange)}}
  .k-month .kpi-num    {{color:var(--blue)}}
  .k-closed .kpi-num   {{color:var(--purple)}}
  .kpi-sub{{font-size:12px;color:var(--muted);margin-top:6px}}

  /* ── Layout ── */
  .layout{{display:grid;grid-template-columns:210px 1fr;
           max-width:1500px;margin:0 auto;padding:0 32px 56px}}

  /* ── Sidebar ── */
  .sidebar{{padding:8px 16px 8px 0;position:sticky;top:65px;
            height:fit-content;max-height:calc(100vh - 90px);overflow-y:auto}}
  .side-title{{font-size:11px;font-weight:600;text-transform:uppercase;
               letter-spacing:.8px;color:var(--muted);margin-bottom:8px;padding:4px 0}}
  .nav-pill{{display:flex;align-items:center;gap:8px;padding:7px 10px;
             border-radius:8px;text-decoration:none;color:var(--muted);
             font-size:13px;margin-bottom:3px;transition:background .12s}}
  .nav-pill:hover{{background:var(--surf2);color:var(--tx)}}
  .nav-init{{width:24px;height:24px;border-radius:6px;background:var(--pill-color,#555);
             color:#fff;font-size:10px;font-weight:700;
             display:flex;align-items:center;justify-content:center;flex-shrink:0}}
  .nav-name{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .nav-ct{{background:var(--surf2);border-radius:10px;padding:1px 7px;
           font-size:11px;color:var(--muted);flex-shrink:0}}

  /* ── Estimator cards ── */
  .feed{{display:flex;flex-direction:column;gap:20px;min-width:0}}
  .est-card{{background:var(--surf);border:1px solid var(--bdr);border-radius:12px;overflow:hidden}}
  .card-hdr{{display:flex;align-items:center;gap:12px;padding:13px 20px;
             border-bottom:1px solid var(--bdr);border-left:4px solid var(--cc,#555)}}
  .avatar{{width:36px;height:36px;border-radius:10px;background:var(--cc,#555);
           color:#fff;font-size:13px;font-weight:700;
           display:flex;align-items:center;justify-content:center;flex-shrink:0}}
  .card-name{{font-size:15px;font-weight:600}}
  .card-sub{{font-size:12px;color:var(--muted)}}

  /* ── Table ── */
  .tbl-wrap{{overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{text-align:left;padding:8px 14px;font-size:11px;font-weight:600;
      text-transform:uppercase;letter-spacing:.5px;color:var(--muted);
      background:rgba(0,0,0,.2);border-bottom:1px solid var(--bdr)}}
  td{{padding:10px 14px;border-bottom:1px solid rgba(51,65,85,.5);vertical-align:top}}
  tr:last-child td{{border-bottom:none}}
  tr.row-new{{background:var(--green-bg)}}
  tr:hover td{{background:rgba(255,255,255,.02)}}
  .td-job{{font-family:monospace;font-weight:600;white-space:nowrap}}
  .td-desc{{color:var(--muted);max-width:300px}}
  .td-loc{{color:var(--muted);white-space:nowrap}}
  .td-days{{font-weight:700;text-align:center;white-space:nowrap}}
  .age-ok{{color:var(--green)}}
  .age-warning{{color:var(--amber)}}
  .age-critical{{color:var(--red)}}
  .badge-new{{display:inline-block;background:var(--green);color:#fff;
              font-size:9px;font-weight:800;letter-spacing:.5px;
              padding:1px 5px;border-radius:4px;margin-left:5px;vertical-align:middle}}

  /* ── Footer ── */
  .footer{{text-align:center;padding:20px 32px;color:var(--muted);
           font-size:12px;border-top:1px solid var(--bdr);max-width:1500px;margin:0 auto}}

  @media(max-width:1000px){{
    .kpis{{grid-template-columns:repeat(2,1fr);padding:16px}}
    .layout{{grid-template-columns:1fr;padding:0 16px 48px}}
    .sidebar{{display:none}}
  }}
  @media(max-width:500px){{
    .kpis{{grid-template-columns:1fr}}
  }}
</style>
</head>
<body>

<!-- Password Gate -->
<div id="gate">
  <div class="gate-box">
    <div class="gate-logo">Winmar <em>Emergency</em></div>
    <div class="gate-sub">Enter password to access dashboard</div>
    <input type="password" id="pwInput" placeholder="Password" onkeydown="if(event.key==='Enter')checkPw()">
    <button onclick="checkPw()">Access Dashboard</button>
    <div class="gate-err" id="pwErr">Incorrect password. Try again.</div>
  </div>
</div>

<script>
(function(){{
  if(sessionStorage.getItem('emDash')==='ok'){{
    document.getElementById('gate').style.display='none';
  }}
  window.checkPw=function(){{
    var v=document.getElementById('pwInput').value;
    if(v==='restore123'){{
      sessionStorage.setItem('emDash','ok');
      document.getElementById('gate').style.display='none';
    }} else {{
      document.getElementById('pwErr').style.display='block';
      document.getElementById('pwInput').value='';
      document.getElementById('pwInput').focus();
    }}
  }};
}})();
</script>

<div class="topbar">
  <div class="logo">Winmar <em>Emergency</em> Dashboard</div>
  <div class="report-meta">
    Report date: {pretty_date} &nbsp;&middot;&nbsp; {total_active} active files<br>
    <span style="font-size:11px;opacity:.7">Updated {now_str}</span>
  </div>
</div>

<div class="kpis">
  <div class="kpi k-new">
    <div class="kpi-lbl">New Today</div>
    <div class="kpi-num">{new_count}</div>
    <div class="kpi-sub">First appearance in today's report</div>
  </div>
  <div class="kpi k-progress">
    <div class="kpi-lbl">In Progress</div>
    <div class="kpi-num">{total_active}</div>
    <div class="kpi-sub">Active jobs on today's report</div>
  </div>
  <div class="kpi k-month">
    <div class="kpi-lbl">Total This Month</div>
    <div class="kpi-num">{total_month}</div>
    <div class="kpi-sub">Unique jobs opened in {format_report_date(report_date).split()[0]}</div>
  </div>
  <div class="kpi k-closed">
    <div class="kpi-lbl">Closed This Month</div>
    <div class="kpi-num">{closed_count}</div>
    <div class="kpi-sub">Resolved and removed this month</div>
  </div>
</div>

<div class="layout">
  <nav class="sidebar">
    <div class="side-title">Estimators</div>

{chr(10).join(sidebar_pills)}
  </nav>

  <div class="feed">

{chr(10).join(cards)}

  </div>
</div>

<div class="footer">
  Refreshed daily at 5:00 PM &nbsp;&middot;&nbsp; Winmar Restoration &nbsp;&middot;&nbsp; {now_str}
</div>
</body>
</html>'''


def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Get today's report date from the latest snapshot
    latest = (
        sb.table("daily_snapshots")
        .select("*")
        .order("report_date", desc=True)
        .limit(1)
        .execute()
    )
    if not latest.data:
        print("No snapshots found. Run parse_report.py first.")
        return

    snapshot = latest.data[0]
    report_date = snapshot["report_date"]
    today_job_numbers = snapshot["job_numbers"]

    # Get new job numbers (first_seen_date == report_date)
    new_result = (
        sb.table("emergency_jobs")
        .select("job_number")
        .eq("first_seen_date", report_date)
        .execute()
    )
    new_job_numbers = [r["job_number"] for r in new_result.data]

    # Get all active jobs
    active = (
        sb.table("emergency_jobs")
        .select("*")
        .eq("is_active", True)
        .execute()
    )
    active_jobs = active.data

    # Get total unique jobs this month (active + closed)
    month_start = report_date[:7] + "-01"
    all_month = (
        sb.table("emergency_jobs")
        .select("job_number")
        .gte("first_seen_date", month_start)
        .lte("first_seen_date", report_date)
        .execute()
    )
    total_month_from_db = len(all_month.data)

    # Get total closed this month
    month_snapshots = (
        sb.table("daily_snapshots")
        .select("closed_count")
        .gte("report_date", month_start)
        .lte("report_date", report_date)
        .execute()
    )
    total_closed_month = sum(s["closed_count"] for s in month_snapshots.data)

    # Override snapshot values with month-level totals
    snapshot["closed_count"] = total_closed_month

    html = build_html(active_jobs, snapshot, new_job_numbers, report_date)

    # Patch in correct month total (replace placeholder)
    # The total_month in build_html uses job count; override with DB value
    total_active = snapshot["total_active"]
    html = html.replace(
        f'<div class="kpi-num">{len(active_jobs)}</div>\n    <div class="kpi-sub">Unique jobs',
        f'<div class="kpi-num">{total_month_from_db}</div>\n    <div class="kpi-sub">Unique jobs',
    ) if total_month_from_db != len(active_jobs) else html

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard written to {OUTPUT_FILE} and {INDEX_FILE}")
    print(f"  Date: {report_date}  Active: {total_active}  New: {snapshot['new_count']}  Closed: {total_closed_month}")


if __name__ == "__main__":
    main()
