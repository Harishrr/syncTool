from fastapi import APIRouter, Depends
from app.models import User
from app.schemas import DatabaseTestRequest
from app.auth.dependencies import require_admin
from app.database import get_active_db_info, test_postgres_connection, switch_to_postgres

router = APIRouter(prefix="/system", tags=["System & Database Configuration"])

@router.get("/db-info")
def get_db_info(admin: User = Depends(require_admin)):
    return get_active_db_info()

@router.post("/test-postgres")
def test_postgres(payload: DatabaseTestRequest, admin: User = Depends(require_admin)):
    success, message = test_postgres_connection(
        user=payload.user,
        password=payload.password,
        host=payload.host,
        port=payload.port,
        dbname=payload.dbname
    )
    return {"success": success, "message": message}

@router.post("/apply-postgres")
def apply_postgres(payload: DatabaseTestRequest, admin: User = Depends(require_admin)):
    success, message = switch_to_postgres(
        user=payload.user,
        password=payload.password,
        host=payload.host,
        port=payload.port,
        dbname=payload.dbname
    )
    return {"success": success, "message": message}

