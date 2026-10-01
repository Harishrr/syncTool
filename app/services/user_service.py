from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import User
from app.schemas import UserCreate, UserUpdate
from app.auth.security import hash_password
from app.config import settings
from app.services.log_service import record_log

def seed_initial_admin(db: Session):
    existing_admin = db.query(User).filter(
        (User.username == settings.DEFAULT_ADMIN_USERNAME) | 
        (User.email == settings.DEFAULT_ADMIN_EMAIL)
    ).first()
    
    if not existing_admin:
        admin_user = User(
            username=settings.DEFAULT_ADMIN_USERNAME,
            email=settings.DEFAULT_ADMIN_EMAIL,
            hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
            totp_enabled=False
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        record_log(
            db,
            level="INFO",
            category="AUTH",
            action="INITIAL_ADMIN_SEEDED",
            details=f"Default admin account '{settings.DEFAULT_ADMIN_USERNAME}' created.",
            user_id=admin_user.id,
            username=admin_user.username
        )
        return admin_user
    return existing_admin

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username_or_email(db: Session, identifier: str) -> Optional[User]:
    return db.query(User).filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user_in: UserCreate, created_by_id: Optional[int] = None) -> User:
    new_user = User(
        username=user_in.username.strip(),
        email=user_in.email.strip().lower(),
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=True,
        totp_enabled=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    record_log(
        db,
        level="INFO",
        category="USER_MGMT",
        action="USER_CREATED",
        details=f"User '{new_user.username}' (Role: {new_user.role}) created.",
        user_id=created_by_id
    )
    return new_user

def update_user(db: Session, user_id: int, user_in: UserUpdate, updated_by_id: Optional[int] = None) -> Optional[User]:
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    if user_in.email is not None:
        user.email = user_in.email.strip().lower()
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.password:
        user.hashed_password = hash_password(user_in.password)

    db.commit()
    db.refresh(user)

    record_log(
        db,
        level="INFO",
        category="USER_MGMT",
        action="USER_UPDATED",
        details=f"User '{user.username}' (ID: {user.id}) updated.",
        user_id=updated_by_id
    )
    return user

from app.auth.totp import generate_totp_secret

def reset_user_password(db: Session, user_id: int, new_password: str, admin_id: Optional[int] = None) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    user.hashed_password = hash_password(new_password)
    db.commit()

    record_log(
        db,
        level="WARNING",
        category="USER_MGMT",
        action="USER_PASSWORD_RESET",
        details=f"Password for user '{user.username}' (ID: {user.id}) was reset by admin.",
        user_id=admin_id
    )
    return True

def toggle_user_2fa(db: Session, user_id: int, enabled: bool, admin_id: Optional[int] = None) -> Optional[User]:
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.totp_enabled = enabled
    if enabled and not user.totp_secret:
        user.totp_secret = generate_totp_secret()
    db.commit()
    db.refresh(user)

    action_str = "USER_2FA_ENABLED" if enabled else "USER_2FA_DISABLED"
    details_str = f"Google 2FA set to {'ACTIVE' if enabled else 'DISABLED'} for user '{user.username}' by admin."
    record_log(
        db,
        level="INFO" if enabled else "WARNING",
        category="USER_MGMT",
        action=action_str,
        details=details_str,
        user_id=admin_id
    )
    return user

def reset_user_2fa(db: Session, user_id: int, admin_id: Optional[int] = None) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    user.totp_secret = None
    user.totp_enabled = False
    db.commit()

    record_log(
        db,
        level="WARNING",
        category="USER_MGMT",
        action="USER_2FA_RESET",
        details=f"2FA credentials reset for user '{user.username}' by admin.",
        user_id=admin_id
    )
    return True

def delete_user(db: Session, user_id: int, admin_id: Optional[int] = None) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    username = user.username

    from app.models import SystemLog, JobRun
    db.query(SystemLog).filter(SystemLog.user_id == user_id).update({"user_id": None})
    db.query(JobRun).filter(JobRun.user_id == user_id).update({"user_id": None})

    db.delete(user)
    db.commit()

    record_log(
        db,
        level="WARNING",
        category="USER_MGMT",
        action="USER_DELETED",
        details=f"User '{username}' (ID: {user_id}) permanently removed.",
        user_id=admin_id
    )
    return True
