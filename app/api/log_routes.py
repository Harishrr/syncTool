from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import User
from app.schemas import SystemLogOut
from app.auth.dependencies import require_admin
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["Log Management"])

@router.get("", response_model=dict)
def view_logs(
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    logs, total = log_service.get_logs(
        db, level=level, category=category, search=search,
        start_date=start_date, end_date=end_date, skip=skip, limit=limit
    )
    return {
        "logs": [SystemLogOut.model_validate(l) for l in logs],
        "total": total
    }

@router.get("/raw")
def view_raw_file_logs(
    lines: int = 300,
    admin: User = Depends(require_admin)
):
    content = log_service.get_raw_log_file_content(lines=lines)
    return {"content": content}

@router.get("/download")
def download_log_file(
    admin: User = Depends(require_admin)
):
    content = log_service.get_raw_log_file_content(lines=10000)
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=sync_tool_activity.log"}
    )
