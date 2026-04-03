# Emergency Dashboard — App Charter

## Purpose
Live dashboard showing all active Winmar emergency jobs. Auto-refreshes daily from a PDF report, pushes data to Supabase, and deploys to Vercel.

---

## Current State
- **Status:** Live and deployed
- **Live URL:** https://emergency-dashboard-mauve.vercel.app
- **Password:** restore123
- **GitHub:** https://github.com/jayrhode/emergency-dashboard
- **Vercel project:** `emergency-dashboard` (jayrhodes-projects team)
- **Supabase project ID:** `wkxncwgikckyinhrnjrg` (GoGio org)

---

## Data Flow
1. PDF report lands in `Emergency Report/` (FUSE-mounted from Windows)
2. `reference/scripts/parse_report.py` extracts job data → upserts to Supabase → writes `output/today_jobs.json`
3. `reference/scripts/generate_dashboard.py` reads Supabase → builds `emergency_dashboard.html`
4. HTML committed to GitHub → Vercel auto-deploys

---

## Scheduled Automation
- **Task:** `emergency-dashboard-update`
- **Schedule:** Daily at 4:15 PM
- **Skill location:** `Claude/Scheduled/emergency-dashboard-update/SKILL.md`
- ⚠️ See session-log.md for current path issue with Python scripts

---

## Folder Layout
- `Emergency Report/` — FUSE-mounted PDF drop folder (do NOT move)
- `input/` — other files handed to Claude for this project
- `output/` — files Claude produces
- `reference/` — static docs, schema notes
  - `reference/scripts/` — `parse_report.py`, `generate_dashboard.py`
- `docs/` — requirements, API contracts
- `tests/` — smoke tests

---

## Tech Decisions
- Password protection: JS sessionStorage gate in `index.html` (NOT Edge Middleware)
- Vercel config: uses `rewrites` not `routes` in `vercel.json`
- FUSE paths: always use `open(path,'rb') + io.BytesIO` with pdfplumber
- GitHub commits: CM6 browser injection (git push blocked in sandbox)

---

## Open Issues
- Scheduled task `emergency-dashboard-update` SKILL.md needs updating to point to `reference/scripts/` for the Python scripts
