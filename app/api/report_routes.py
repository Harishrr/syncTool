from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import User
from app.schemas import ReportSummaryOut
from app.auth.dependencies import get_current_user
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

@router.get("/summary", response_model=ReportSummaryOut)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return report_service.get_report_summary(db)

@router.get("/history")
def get_history(
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Non-admin users can only view their own history
    target_user_id = user_id if current_user.role == "admin" else current_user.id

    runs, total = report_service.get_job_runs(
        db, user_id=target_user_id, status=status,
        start_date=start_date, end_date=end_date, skip=skip, limit=limit
    )
    return {"runs": runs, "total": total}

@router.get("/export")
def export_csv(
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_user_id = user_id if current_user.role == "admin" else current_user.id
    csv_content = report_service.export_reports_csv(
        db, user_id=target_user_id, status=status,
        start_date=start_date, end_date=end_date
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sync_tool_report.csv"}
    )
