from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # 'admin' or 'user'
    is_active = Column(Boolean, default=True, nullable=False)
    totp_secret = Column(String(64), nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    jobs = relationship("Job", back_populates="creator")
    runs = relationship("JobRun", back_populates="user")
    logs = relationship("SystemLog", back_populates="user")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    transfer_type = Column(String(20), default="robocopy", nullable=False)  # 'robocopy', 'sftp', 'udp'
    source_path = Column(Text, nullable=False)
    dest_path = Column(Text, nullable=False)
    
    # Remote server details (SFTP / UDP)
    host = Column(String(100), nullable=True)
    port = Column(Integer, nullable=True)
    remote_username = Column(String(100), nullable=True)
    remote_password = Column(String(255), nullable=True)
    
    # Overwrite mode: 'newer' (Overwrite only for newer files) or 'always' (Always overwrite)
    overwrite_mode = Column(String(20), default="newer", nullable=False)

    # Execution status & live metrics
    status = Column(String(20), default="pending", index=True, nullable=False) # pending, running, paused, completed, failed, cancelled
    progress = Column(Float, default=0.0)
    bytes_copied = Column(BigInteger, default=0)
    total_bytes = Column(BigInteger, default=0)
    current_file = Column(Text, nullable=True)
    speed_mbps = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    creator = relationship("User", back_populates="jobs")
    runs = relationship("JobRun", back_populates="job", cascade="all, delete-orphan")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, cancelled
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, default=0.0)
    bytes_transferred = Column(BigInteger, default=0)
    files_copied = Column(Integer, default=0)
    exit_code = Column(Integer, default=0)
    log_output = Column(Text, nullable=True)

    job = relationship("Job", back_populates="runs")
    user = relationship("User", back_populates="runs")

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    level = Column(String(20), default="INFO", index=True, nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    category = Column(String(50), default="SYSTEM", index=True, nullable=False)  # AUTH, JOB, USER_MGMT, SYSTEM
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)

    user = relationship("User", back_populates="logs")
