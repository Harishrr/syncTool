import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.models import SystemLog

# Configure Root and File Logger
logger = logging.getLogger("sync_tool")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Rotating file handler: 10MB per file, keep 5 backups
    file_handler = RotatingFileHandler(
        settings.LOG_FILE_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def record_log(
    db: Session,
    level: str,
    category: str,
    action: str,
    details: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None
):
    # 1. Log to rotating file
    msg = f"[{category}] [{action}] {details}"
    if username:
        msg += f" (User: {username})"
    if ip_address:
        msg += f" (IP: {ip_address})"

    log_level_map = {
        "DEBUG": logger.debug,
        "INFO": logger.info,
        "WARNING": logger.warning,
        "ERROR": logger.error,
        "CRITICAL": logger.critical
    }
    log_func = log_level_map.get(level.upper(), logger.info)
    log_func(msg)

    # 2. Log to Database
    try:
        sys_log = SystemLog(
            timestamp=datetime.now(timezone.utc),
            level=level.upper(),
            category=category.upper(),
            action=action,
            details=details,
            user_id=user_id,
            username=username,
            ip_address=ip_address
        )
        db.add(sys_log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to record log to DB: {e}")

def get_logs(
    db: Session,
    level: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[SystemLog], int]:
    query = db.query(SystemLog)

    if level and level.upper() != "ALL":
        query = query.filter(SystemLog.level == level.upper())
    if category and category.upper() != "ALL":
        query = query.filter(SystemLog.category == category.upper())
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (SystemLog.action.ilike(search_pattern)) | 
            (SystemLog.details.ilike(search_pattern)) | 
            (SystemLog.username.ilike(search_pattern))
        )
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(SystemLog.timestamp >= sd)
        except Exception:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(SystemLog.timestamp <= ed)
        except Exception:
            pass

    total = query.count()
    logs = query.order_by(desc(SystemLog.timestamp)).offset(skip).limit(limit).all()
    return logs, total

def get_raw_log_file_content(lines: int = 500) -> str:
    if not os.path.exists(settings.LOG_FILE_PATH):
        return "Log file empty or not created yet."
    try:
        with open(settings.LOG_FILE_PATH, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading log file: {e}"
