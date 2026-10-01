from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserUpdate, UserOut
from app.auth.dependencies import require_admin
from app.services import user_service

router = APIRouter(prefix="/users", tags=["User Management"])

@router.get("", response_model=List[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 100,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = user_service.get_all_users(db, skip=skip, limit=limit)
    return [UserOut.model_validate(u) for u in users]

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_new_user(
    payload: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    existing = user_service.get_user_by_username_or_email(db, payload.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken.")
    
    existing_email = user_service.get_user_by_username_or_email(db, payload.email)
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already in use.")

    new_user = user_service.create_user(db, payload, created_by_id=admin.id)
    return UserOut.model_validate(new_user)

@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    updated = user_service.update_user(db, user_id, payload, updated_by_id=admin.id)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(updated)

from app.schemas import UserCreate, UserUpdate, UserOut, UserResetPassword, UserToggle2FA

@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: UserResetPassword,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin resets a user's password directly."""
    success = user_service.reset_user_password(db, user_id, payload.new_password, admin_id=admin.id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User password reset successfully."}

@router.post("/{user_id}/toggle-2fa", response_model=UserOut)
def toggle_2fa(
    user_id: int,
    payload: UserToggle2FA,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin activates or disables Google 2FA for a user."""
    updated = user_service.toggle_user_2fa(db, user_id, payload.enabled, admin_id=admin.id)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(updated)

@router.post("/{user_id}/reset-2fa")
def reset_2fa(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    success = user_service.reset_user_2fa(db, user_id, admin_id=admin.id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Two-factor authentication credentials reset successfully."}

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account.")
    
    success = user_service.delete_user(db, user_id, admin_id=admin.id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully."}
