from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# ----------------- Auth & User Schemas -----------------
class UserLogin(BaseModel):
    username_or_email: str
    password: str

class TOTPVerify(BaseModel):
    temp_token: str
    code: str

class TOTPSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code_base64: str

class TOTPEnableRequest(BaseModel):
    secret: str
    code: str

EMAIL_REGEX = r"^[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z0-9\-]+$"

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=EMAIL_REGEX)
    password: str = Field(..., min_length=6)
    role: str = Field(default="user", pattern="^(admin|user)$")

class UserUpdate(BaseModel):
    email: Optional[str] = Field(default=None, pattern=EMAIL_REGEX)
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserResetPassword(BaseModel):
    new_password: str = Field(..., min_length=6)

class UserToggle2FA(BaseModel):
    enabled: bool

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    totp_enabled: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class LoginResponse(BaseModel):
    requires_2fa: bool
    temp_token: Optional[str] = None
    auth_data: Optional[TokenOut] = None

# ----------------- Job Schemas -----------------
class JobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    transfer_type: str = Field(default="robocopy", pattern="^(robocopy|sftp|udp)$")
    source_path: str
    dest_path: str
    overwrite_mode: Optional[str] = Field(default="newer", pattern="^(newer|always)$")
    host: Optional[str] = None
    port: Optional[int] = None
    remote_username: Optional[str] = None
    remote_password: Optional[str] = None

class JobUpdate(BaseModel):
    name: Optional[str] = None
    transfer_type: Optional[str] = None
    source_path: Optional[str] = None
    dest_path: Optional[str] = None
    overwrite_mode: Optional[str] = Field(default=None, pattern="^(newer|always)$")
    host: Optional[str] = None
    port: Optional[int] = None
    remote_username: Optional[str] = None
    remote_password: Optional[str] = None

class JobOut(BaseModel):
    id: int
    name: str
    transfer_type: str
    source_path: str
    dest_path: str
    overwrite_mode: Optional[str] = "newer"
    host: Optional[str] = None
    port: Optional[int] = None
    remote_username: Optional[str] = None
    status: str
    progress: float
    bytes_copied: int
    total_bytes: int
    current_file: Optional[str] = None
    speed_mbps: float
    error_message: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ----------------- Log Schemas -----------------
class SystemLogOut(BaseModel):
    id: int
    timestamp: datetime
    level: str
    category: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    details: Optional[str] = None
    ip_address: Optional[str] = None

    class Config:
        from_attributes = True

# ----------------- Report & History Schemas -----------------
class JobRunOut(BaseModel):
    id: int
    job_id: int
    job_name: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float
    bytes_transferred: int
    files_copied: int
    exit_code: int
    log_output: Optional[str] = None

    class Config:
        from_attributes = True

class ReportSummaryOut(BaseModel):
    total_jobs: int
    successful_runs: int
    failed_runs: int
    running_jobs: int
    total_bytes_transferred: int
    total_files_transferred: int

# ----------------- Database Info / Test -----------------
class DatabaseTestRequest(BaseModel):
    user: str
    password: str
    host: str = "localhost"
    port: int = 5432
    dbname: str = "synctool_db"
