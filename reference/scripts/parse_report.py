"""
parse_report.py — Extract jobs from the latest Emergency Production Report PDF
and upsert into Supabase (emergency_jobs + daily_snapshots).

Usage:  python parse_report.py
Reads:  .env.local for SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
"""

import io, os, re, json, glob
from datetime import date, datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import pdfplumber
from supabase import create_client

# ── Config ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent          # emergency-dashboard/
REPORT_DIR = PROJECT_DIR / "Emergency Report"

load_dotenv(PROJECT_DIR / ".env.local")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def find_latest_pdf():
    """Return the most recent readable PDF by filename date stamp.
    Falls back to the most recent readable file if the latest is a
    cloud-only OneDrive placeholder (FUSE errno 22)."""
    pdfs = sorted(glob.glob(str(REPORT_DIR / "*.pdf")), reverse=True)
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {REPORT_DIR}")
    for pdf_path in pdfs:
        try:
            with open(pdf_path, "rb") as f:
                f.read(4)  # probe readability
            return pdf_path
        except OSError:
            print(f"Skipping unreadable (cloud placeholder?): {os.path.basename(pdf_path)}")
    raise FileNotFoundError(f"No readable PDFs found in {REPORT_DIR}")


def extract_jobs(pdf_path: str) -> list[dict]:
    """Parse the PDF table into a list of job dicts."""
    # Use open + BytesIO for FUSE-mounted paths
    with open(pdf_path, "rb") as f:
        pdf_bytes = io.BytesIO(f.read())

    jobs = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            for row in table:
                # Skip header rows and summary rows
                if not row or not row[0] or "Date Received" in str(row[0]):
                    continue
                # Skip the summary row (e.g. "11.00 Jobs In Progress")
                if re.match(r"^\d+\.\d+$", str(row[0]).strip()):
                    break

                date_received_raw = str(row[0]).strip()
                job_number = str(row[1]).strip()
                estimator = str(row[2]).strip()
                customer = str(row[3]).strip()
                address = str(row[4]).strip()
                city = str(row[5]).strip()
                description = str(row[6]).strip()
                days_open_raw = str(row[7]).strip() if len(row) > 7 else "0"

                # Skip if no valid job number
                if not job_number or job_number == "None":
                    continue

                # Parse date_received — ISO format "2025-11-04T12:21:59"
                date_received = date_received_raw[:10]

                # Parse days open — "147 Days <br />11/04/2025 to Present"
                days_match = re.match(r"(\d+)", days_open_raw)
                days_open = int(days_match.group(1)) if days_match else 0

                # Clean customer name — remove trailing ", ."
                customer = re.sub(r",\s*\.\s*$", "", customer).strip()

                jobs.append({
                    "job_number": job_number,
                    "estimator": estimator,
                    "customer": customer,
                    "address": address,
                    "city": city,
                    "description": description,
                    "date_received": date_received,
                    "days_open": days_open,
                })

    return jobs


def extract_report_date(pdf_path: str) -> str:
    """Pull the report date from the filename (YYYY-MM-DD)."""
    basename = os.path.basename(pdf_path)
    match = re.match(r"(\d{4}-\d{2}-\d{2})", basename)
    if match:
        return match.group(1)
    return str(date.today())


def upsert_jobs(sb, jobs: list[dict], report_date: str):
    """Upsert jobs into emergency_jobs and update active status."""
    today_job_numbers = [j["job_number"] for j in jobs]

    # Get yesterday's snapshot to determine new/closed
    prev = (
        sb.table("daily_snapshots")
        .select("job_numbers")
        .lt("report_date", report_date)
        .order("report_date", desc=True)
        .limit(1)
        .execute()
    )
    prev_job_numbers = prev.data[0]["job_numbers"] if prev.data else []

    new_jobs = [j for j in today_job_numbers if j not in prev_job_numbers]
    closed_jobs = [j for j in prev_job_numbers if j not in today_job_numbers]

    # Upsert each active job
    for job in jobs:
        row = {
            **job,
            "last_seen_date": report_date,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # For brand-new jobs, set first_seen_date
        if job["job_number"] in new_jobs:
            row["first_seen_date"] = report_date
            row["created_at"] = datetime.now(timezone.utc).isoformat()

        existing = (
            sb.table("emergency_jobs")
            .select("first_seen_date")
            .eq("job_number", job["job_number"])
            .execute()
        )
        if existing.data:
            # Update existing — preserve first_seen_date
            row.pop("first_seen_date", None)
            row.pop("created_at", None)
            sb.table("emergency_jobs").update(row).eq("job_number", job["job_number"]).execute()
        else:
            row["first_seen_date"] = row.get("first_seen_date", report_date)
            row["created_at"] = row.get("created_at", datetime.now(timezone.utc).isoformat())
            sb.table("emergency_jobs").insert(row).execute()

    # Mark closed jobs
    for jn in closed_jobs:
        sb.table("emergency_jobs").update({
            "is_active": False,
            "last_seen_date": report_date,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("job_number", jn).execute()

    # Upsert daily snapshot
    sb.table("daily_snapshots").upsert({
        "report_date": report_date,
        "job_numbers": today_job_numbers,
        "new_count": len(new_jobs),
        "closed_count": len(closed_jobs),
        "total_active": len(today_job_numbers),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    return new_jobs, closed_jobs


def main():
    pdf_path = find_latest_pdf()
    report_date = extract_report_date(pdf_path)
    print(f"Processing: {os.path.basename(pdf_path)}  (date: {report_date})")

    jobs = extract_jobs(pdf_path)
    print(f"Extracted {len(jobs)} jobs from PDF")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    new_jobs, closed_jobs = upsert_jobs(sb, jobs, report_date)

    print(f"New:    {len(new_jobs)}  {new_jobs}")
    print(f"Closed: {len(closed_jobs)}  {closed_jobs}")
    print(f"Active: {len(jobs)}")

    # Write jobs to temp JSON for generate_dashboard.py
    out_path = PROJECT_DIR / "output" / "today_jobs.json"
    with open(out_path, "w") as f:
        json.dump({"report_date": report_date, "jobs": jobs,
                    "new_jobs": new_jobs, "closed_jobs": closed_jobs}, f, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
