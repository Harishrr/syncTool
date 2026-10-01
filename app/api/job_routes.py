from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import User
from app.schemas import JobCreate, JobUpdate, JobOut
from app.auth.dependencies import get_current_user
from app.services import job_service
from app.engines.orchestrator import orchestrator

router = APIRouter(prefix="/jobs", tags=["Jobs Management"])

@router.get("", response_model=dict)
def list_jobs(
    status: Optional[str] = Query(None, description="success, failed, upcoming, paused, running, cancelled"),
    transfer_type: Optional[str] = Query(None, description="robocopy, sftp, udp"),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    jobs, total = job_service.get_jobs(
        db, status=status, transfer_type=transfer_type, search=search,
        start_date=start_date, end_date=end_date, skip=skip, limit=limit
    )
    return {
        "jobs": [JobOut.model_validate(j) for j in jobs],
        "total": total
    }

@router.post("", response_model=JobOut)
def create_job(
    payload: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = job_service.create_job(db, payload, user_id=current_user.id)
    return JobOut.model_validate(job)

@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = job_service.get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)

@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = job_service.update_job(db, job_id, payload, user_id=current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Stop if running
    orchestrator.stop_job(job_id)
    success = job_service.delete_job(db, job_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted successfully."}

# ----------------- Execution Controls -----------------

@router.post("/{job_id}/start")
def start_job(
    job_id: int,
    current_user: User = Depends(get_current_user)
):
    success = orchestrator.start_job(job_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Could not start job. Check if already running or invalid.")
    return {"message": f"Job {job_id} started."}

@router.post("/{job_id}/pause")
def pause_job(
    job_id: int,
    current_user: User = Depends(get_current_user)
):
    success = orchestrator.pause_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Could not pause job. Job may not be currently running.")
    return {"message": f"Job {job_id} paused."}

@router.post("/{job_id}/resume")
def resume_job(
    job_id: int,
    current_user: User = Depends(get_current_user)
):
    success = orchestrator.resume_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Could not resume job. Job may not be paused.")
    return {"message": f"Job {job_id} resumed."}

@router.post("/{job_id}/stop")
def stop_job(
    job_id: int,
    current_user: User = Depends(get_current_user)
):
    success = orchestrator.stop_job(job_id)
    return {"message": f"Job {job_id} stop requested."}

# ----------------- Bulk Job Controls -----------------

@router.post("/bulk/start-all")
def start_all_jobs(current_user: User = Depends(get_current_user)):
    started = orchestrator.start_all_jobs(user_id=current_user.id)
    return {"started_count": len(started), "job_ids": started}

@router.post("/bulk/pause-all")
def pause_all_jobs(current_user: User = Depends(get_current_user)):
    paused = orchestrator.pause_all_jobs()
    return {"paused_count": len(paused), "job_ids": paused}

@router.post("/bulk/resume-all")
def resume_all_jobs(current_user: User = Depends(get_current_user)):
    resumed = orchestrator.resume_all_jobs()
    return {"resumed_count": len(resumed), "job_ids": resumed}

@router.post("/bulk/stop-all")
def stop_all_jobs(current_user: User = Depends(get_current_user)):
    stopped = orchestrator.stop_all_jobs()
    return {"stopped_count": len(stopped), "job_ids": stopped}

# ----------------- CSV Import / Template -----------------

@router.post("/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    try:
        csv_text = contents.decode("utf-8-sig")  # handles potential BOM from Excel
    except UnicodeDecodeError:
        csv_text = contents.decode("latin-1", errors="replace")

    result = job_service.import_jobs_from_csv(db, csv_text, user_id=current_user.id)
    return result

@router.get("/csv-template")
def download_csv_template():
    csv_data = job_service.generate_csv_template()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sync_tool_jobs_template.csv"}
    )
