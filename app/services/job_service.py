import csv
import io
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Job, JobRun
from app.schemas import JobCreate, JobUpdate
from app.services.log_service import record_log

def get_jobs(
    db: Session,
    status: Optional[str] = None,
    transfer_type: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[Job], int]:
    query = db.query(Job)

    if status and status.lower() != "all":
        st = status.lower()
        if st == "success":
            query = query.filter(Job.status == "completed")
        elif st == "upcoming":
            query = query.filter(Job.status == "pending")
        else:
            query = query.filter(Job.status == st)

    if transfer_type and transfer_type.lower() != "all":
        query = query.filter(Job.transfer_type == transfer_type.lower())

    if search:
        search_pat = f"%{search}%"
        query = query.filter(
            (Job.name.ilike(search_pat)) | 
            (Job.source_path.ilike(search_pat)) | 
            (Job.dest_path.ilike(search_pat))
        )

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(Job.created_at >= sd)
        except Exception:
            pass

    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(Job.created_at <= ed)
        except Exception:
            pass

    total = query.count()
    jobs = query.order_by(desc(Job.created_at)).offset(skip).limit(limit).all()
    return jobs, total

def get_job_by_id(db: Session, job_id: int) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_id).first()

def create_job(db: Session, job_in: JobCreate, user_id: Optional[int] = None) -> Job:
    new_job = Job(
        name=job_in.name,
        transfer_type=job_in.transfer_type,
        source_path=job_in.source_path,
        dest_path=job_in.dest_path,
        overwrite_mode=job_in.overwrite_mode or "newer",
        host=job_in.host,
        port=job_in.port,
        remote_username=job_in.remote_username,
        remote_password=job_in.remote_password,
        status="pending",
        progress=0.0,
        bytes_copied=0,
        total_bytes=0,
        speed_mbps=0.0,
        created_by_id=user_id
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    record_log(
        db,
        level="INFO",
        category="JOB",
        action="JOB_CREATED",
        details=f"Job '{new_job.name}' ({new_job.transfer_type}, overwrite: {new_job.overwrite_mode}) created.",
        user_id=user_id
    )
    return new_job

def update_job(db: Session, job_id: int, job_in: JobUpdate, user_id: Optional[int] = None) -> Optional[Job]:
    job = get_job_by_id(db, job_id)
    if not job:
        return None

    update_data = job_in.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(job, k, v)

    db.commit()
    db.refresh(job)

    record_log(
        db,
        level="INFO",
        category="JOB",
        action="JOB_UPDATED",
        details=f"Job '{job.name}' updated.",
        user_id=user_id
    )
    return job

def delete_job(db: Session, job_id: int, user_id: Optional[int] = None) -> bool:
    job = get_job_by_id(db, job_id)
    if not job:
        return False
    name = job.name
    db.delete(job)
    db.commit()

    record_log(
        db,
        level="WARNING",
        category="JOB",
        action="JOB_DELETED",
        details=f"Job '{name}' (ID: {job_id}) deleted.",
        user_id=user_id
    )
    return True

def import_jobs_from_csv(db: Session, csv_content: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    f = io.StringIO(csv_content.strip())
    reader = csv.DictReader(f)
    
    imported = []
    errors = []
    
    row_num = 1
    for row in reader:
        row_num += 1
        name = row.get("name", "").strip()
        transfer_type = row.get("transfer_type", "robocopy").strip().lower()
        source_path = row.get("source_path", "").strip()
        dest_path = row.get("dest_path", "").strip()
        overwrite_mode = row.get("overwrite_mode", "newer").strip().lower() or "newer"
        if overwrite_mode not in ("newer", "always"):
            overwrite_mode = "newer"
        host = row.get("host", "").strip() or None
        port_raw = row.get("port", "").strip()
        remote_username = row.get("remote_username", "").strip() or None
        remote_password = row.get("remote_password", "").strip() or None

        if not name or not source_path or not dest_path:
            errors.append(f"Row {row_num}: Name, source_path, and dest_path are required.")
            continue

        if transfer_type not in ("robocopy", "sftp", "udp"):
            errors.append(f"Row {row_num}: Invalid transfer_type '{transfer_type}'. Must be robocopy, sftp, or udp.")
            continue

        port = None
        if port_raw:
            try:
                port = int(port_raw)
            except ValueError:
                errors.append(f"Row {row_num}: Port must be an integer.")
                continue

        job = Job(
            name=name,
            transfer_type=transfer_type,
            source_path=source_path,
            dest_path=dest_path,
            overwrite_mode=overwrite_mode,
            host=host,
            port=port,
            remote_username=remote_username,
            remote_password=remote_password,
            status="pending",
            progress=0.0,
            created_by_id=user_id
        )
        db.add(job)
        imported.append(name)

    if imported:
        db.commit()
        record_log(
            db,
            level="INFO",
            category="JOB",
            action="CSV_IMPORT",
            details=f"Imported {len(imported)} jobs from CSV.",
            user_id=user_id
        )

    return {
        "imported_count": len(imported),
        "imported_jobs": imported,
        "errors": errors
    }

def generate_csv_template() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "name", "transfer_type", "source_path", "dest_path", 
        "host", "port", "remote_username", "remote_password"
    ])
    writer.writerow([
        "Local Robocopy Backup", "robocopy", "C:\\SourceFolder", "D:\\BackupFolder",
        "", "", "", ""
    ])
    writer.writerow([
        "SFTP Offsite Sync", "sftp", "C:\\DataToUpload", "/remote/backup",
        "192.168.1.50", "22", "backup_user", "SecretPass123"
    ])
    writer.writerow([
        "High-Speed UDP Pipe", "udp", "C:\\LargeStream", "/remote/incoming",
        "192.168.1.60", "9999", "", ""
    ])
    return output.getvalue()
