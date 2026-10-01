from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.models import User
from app.schemas import (
    UserLogin, TOTPVerify, TOTPSetupResponse, TOTPEnableRequest, 
    TokenOut, LoginResponse, UserOut
)
from app.auth.security import (
    verify_password, create_access_token, create_temp_2fa_token, decode_token
)
from app.auth.totp import (
    generate_totp_secret, get_provisioning_uri, generate_qr_code_base64, verify_totp_code
)
from app.auth.dependencies import get_current_user
from app.services.log_service import record_log

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=LoginResponse)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    identifier = payload.username_or_email.strip()
    user = db.query(User).filter(
        (User.username == identifier) | (User.email == identifier.lower())
    ).first()

    ip = request.client.host if request.client else None

    if not user or not verify_password(payload.password, user.hashed_password):
        record_log(
            db, level="WARNING", category="AUTH", action="LOGIN_FAILED",
            details=f"Failed login attempt for '{identifier}'",
            ip_address=ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator."
        )

    # Check if Google Authenticator 2FA is required
    if user.totp_enabled and user.totp_secret:
        temp_token = create_temp_2fa_token(user.id)
        record_log(
            db, level="INFO", category="AUTH", action="2FA_CHALLENGE",
            details=f"User '{user.username}' prompted for Google Authenticator TOTP.",
            user_id=user.id, username=user.username, ip_address=ip
        )
        return LoginResponse(requires_2fa=True, temp_token=temp_token)

    # Regular login
    access_token = create_access_token(data={"sub": str(user.id), "username": user.username, "role": user.role})
    record_log(
        db, level="INFO", category="AUTH", action="LOGIN_SUCCESS",
        details=f"User '{user.username}' successfully authenticated.",
        user_id=user.id, username=user.username, ip_address=ip
    )
    return LoginResponse(
        requires_2fa=False,
        auth_data=TokenOut(
            access_token=access_token,
            token_type="bearer",
            user=UserOut.model_validate(user)
        )
    )

@router.post("/verify-2fa", response_model=TokenOut)
def verify_2fa(payload: TOTPVerify, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    token_data = decode_token(payload.temp_token)
    if not token_data or token_data.get("type") != "2fa_pending":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired 2FA session token")

    user_id = int(token_data.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    if not verify_totp_code(user.totp_secret, payload.code):
        record_log(
            db, level="WARNING", category="AUTH", action="2FA_FAILED",
            details=f"Invalid Google Authenticator code for '{user.username}'",
            user_id=user.id, username=user.username, ip_address=ip
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google Authenticator code")

    access_token = create_access_token(data={"sub": str(user.id), "username": user.username, "role": user.role})
    record_log(
        db, level="INFO", category="AUTH", action="LOGIN_SUCCESS_2FA",
        details=f"User '{user.username}' completed 2FA login.",
        user_id=user.id, username=user.username, ip_address=ip
    )
    return TokenOut(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )

@router.post("/setup-2fa", response_model=TOTPSetupResponse)
def setup_2fa(current_user: User = Depends(get_current_user)):
    secret = generate_totp_secret()
    uri = get_provisioning_uri(current_user.username, secret)
    qr_code = generate_qr_code_base64(uri)
    return TOTPSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_code_base64=qr_code
    )

@router.post("/confirm-2fa")
def confirm_2fa(payload: TOTPEnableRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_totp_code(payload.secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code does not match. Check clock or code.")

    current_user.totp_secret = payload.secret
    current_user.totp_enabled = True
    db.commit()

    record_log(
        db, level="INFO", category="AUTH", action="2FA_ENABLED",
        details=f"User '{current_user.username}' enabled Google Authenticator 2FA.",
        user_id=current_user.id, username=current_user.username
    )
    return {"message": "Google Authenticator 2FA enabled successfully."}

@router.post("/disable-2fa")
def disable_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.totp_secret = None
    current_user.totp_enabled = False
    db.commit()

    record_log(
        db, level="INFO", category="AUTH", action="2FA_DISABLED",
        details=f"User '{current_user.username}' disabled 2FA.",
        user_id=current_user.id, username=current_user.username
    )
    return {"message": "Google Authenticator 2FA has been disabled."}

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
