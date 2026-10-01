import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger("sync_tool.database")

Base = declarative_base()

active_db_type = "sqlite"
engine = None
SessionLocal = None

def ensure_schema_upgrades(target_engine):
    try:
        with target_engine.begin() as conn:
            if active_db_type == "postgresql":
                conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS overwrite_mode VARCHAR(20) DEFAULT 'newer';"))
            else:
                try:
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN overwrite_mode VARCHAR(20) DEFAULT 'newer';"))
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Schema upgrade check: {e}")

def init_database():
    global engine, SessionLocal, active_db_type
    
    # First, try PostgreSQL
    try:
        pg_engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 3}
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        engine = pg_engine
        active_db_type = "postgresql"
        ensure_schema_upgrades(engine)
        logger.info(f"Connected to PostgreSQL database successfully at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed ({e}). Falling back to local SQLite: {settings.SQLITE_URL}")
        # Fallback to SQLite
        engine = create_engine(
            settings.SQLITE_URL,
            connect_args={"check_same_thread": False}
        )
        active_db_type = "sqlite"
        ensure_schema_upgrades(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine

# Initialize on module load
init_database()

def get_db():
    if SessionLocal is None:
        init_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_active_db_info():
    return {
        "active_type": active_db_type,
        "postgres_host": settings.POSTGRES_HOST,
        "postgres_port": settings.POSTGRES_PORT,
        "postgres_db": settings.POSTGRES_DB,
        "postgres_user": settings.POSTGRES_USER,
        "sqlite_path": settings.SQLITE_URL
    }

def test_postgres_connection(user, password, host, port, dbname):
    try:
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=user,
            password=password,
            host=host,
            port=int(port) if port else 5432,
            database=dbname
        )
        test_engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "PostgreSQL connection successful!"
    except Exception as e:
        return False, str(e)

def switch_to_postgres(user, password, host, port, dbname):
    global engine, SessionLocal, active_db_type
    try:
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=user,
            password=password,
            host=host,
            port=int(port) if port else 5432,
            database=dbname
        )
        new_engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with new_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Ensure all models are registered before creating tables
        import app.models
        Base.metadata.create_all(bind=new_engine)

        if engine:
            try:
                engine.dispose()
            except Exception:
                pass

        engine = new_engine
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        active_db_type = "postgresql"

        # Update runtime settings
        settings.POSTGRES_USER = user
        settings.POSTGRES_PASSWORD = password
        settings.POSTGRES_HOST = host
        settings.POSTGRES_PORT = str(port)
        settings.POSTGRES_DB = dbname
        settings.DATABASE_URL = url.render_as_string(hide_password=False)

        # Seed initial admin in PostgreSQL if needed
        from app.services.user_service import seed_initial_admin
        db = SessionLocal()
        try:
            seed_initial_admin(db)
        finally:
            db.close()

        logger.info(f"Successfully switched active database to PostgreSQL at {host}:{port}/{dbname}")
        return True, f"Successfully connected and switched active database to PostgreSQL ({dbname})"
    except Exception as e:
        logger.error(f"Failed to switch database to PostgreSQL: {e}")
        return False, str(e)

