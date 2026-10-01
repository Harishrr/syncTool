import os
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

def build_postgres_url(user: str, password: str, host: str, port: str | int, dbname: str) -> str:
    return URL.create(
        drivername="postgresql+psycopg2",
        username=user,
        password=password,
        host=host,
        port=int(port) if port else 5432,
        database=dbname
    ).render_as_string(hide_password=False)

class Settings(BaseModel):
    PROJECT_NAME: str = "Sync Tool"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "synctool-enterprise-super-secret-key-2026-secure")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "Admin@54321")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "synctool_db")
    
    # Custom DATABASE_URL override if provided
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        build_postgres_url(
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "Admin@54321"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "synctool_db")
        )
    )
    
    SQLITE_URL: str = f"sqlite:///{BASE_DIR / 'synctool_local.db'}"
    
    # Logging
    LOG_FILE_PATH: str = str(LOGS_DIR / "sync_tool.log")
    
    # Default Admin
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_EMAIL: str = "admin@synctool.local"
    DEFAULT_ADMIN_PASSWORD: str = "Admin@12345"

settings = Settings()

