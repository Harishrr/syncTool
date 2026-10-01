import csv
import io
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models import Job, JobRun, User
from app.schemas import ReportSummaryOut

def get_report_summary(db: Session) -> ReportSummaryOut:
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    running_jobs = db.query(func.count(Job.id)).filter(Job.status == "running").scalar() or 0
    
    successful_runs = db.query(func.count(JobRun.id)).filter(JobRun.status == "completed").scalar() or 0
    failed_runs = db.query(func.count(JobRun.id)).filter(JobRun.status == "failed").scalar() or 0
    
    total_bytes = db.query(func.sum(JobRun.bytes_transferred)).scalar() or 0
    total_files = db.query(func.sum(JobRun.files_copied)).scalar() or 0

    return ReportSummaryOut(
        total_jobs=total_jobs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        running_jobs=running_jobs,
        total_bytes_transferred=int(total_bytes),
        total_files_transferred=int(total_files)
    )

def get_job_runs(
    db: Session,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[Dict[str, Any]], int]:
    query = db.query(JobRun).join(Job, JobRun.job_id == Job.id, isouter=True).join(User, JobRun.user_id == User.id, isouter=True)

    if user_id:
        query = query.filter(JobRun.user_id == user_id)
    if status and status.lower() != "all":
        st = status.lower()
        if st == "success":
            query = query.filter(JobRun.status == "completed")
        else:
            query = query.filter(JobRun.status == st)

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(JobRun.start_time >= sd)
        except Exception:
            pass

    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(JobRun.start_time <= ed)
        except Exception:
            pass

    total = query.count()
    runs = query.order_by(desc(JobRun.start_time)).offset(skip).limit(limit).all()

    results = []
    for r in runs:
        results.append({
            "id": r.id,
            "job_id": r.job_id,
            "job_name": r.job.name if r.job else "Deleted Job",
            "transfer_type": r.job.transfer_type if r.job else "unknown",
            "user_id": r.user_id,
            "username": r.user.username if r.user else "System",
            "status": r.status,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "end_time": r.end_time.isoformat() if r.end_time else None,
            "duration_seconds": r.duration_seconds,
            "bytes_transferred": r.bytes_transferred,
            "files_copied": r.files_copied,
            "exit_code": r.exit_code,
            "log_output": r.log_output[:500] if r.log_output else None
        })

    return results, total

def export_reports_csv(db: Session, user_id: Optional[int] = None, status: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    runs, _ = get_job_runs(db, user_id=user_id, status=status, start_date=start_date, end_date=end_date, limit=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Run ID", "Job Name", "Protocol", "User", "Status",
        "Start Time", "End Time", "Duration (s)", "Bytes Transferred", "Files Copied", "Exit Code"
    ])

    for r in runs:
        writer.writerow([
            r["id"],
            r["job_name"],
            r["transfer_type"],
            r["username"],
            r["status"],
            r["start_time"],
            r["end_time"],
            r["duration_seconds"],
            r["bytes_transferred"],
            r["files_copied"],
            r["exit_code"]
        ])

    return output.getvalue()
