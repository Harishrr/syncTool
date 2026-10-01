import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_database, SessionLocal, Base, engine
from app.models import User, Job, JobRun, SystemLog
from app.services.user_service import seed_initial_admin
from app.services.log_service import logger
from app.engines.orchestrator import ws_manager

from app.api.auth_routes import router as auth_router
from app.api.user_routes import router as user_router
from app.api.job_routes import router as job_router
from app.api.log_routes import router as log_router
from app.api.report_routes import router as report_router
from app.api.system_routes import router as system_router
from app.api.fs_routes import router as fs_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("Starting Sync Tool backend service...")
    current_engine = init_database()
    Base.metadata.create_all(bind=current_engine)
    
    # Register event loop for WS broadcasts
    loop = asyncio.get_running_loop()
    ws_manager.set_loop(loop)

    # Seed admin user
    db = SessionLocal()
    try:
        seed_initial_admin(db)
    finally:
        db.close()

    logger.info("Sync Tool initialized and ready for connections.")
    yield
    logger.info("Shutting down Sync Tool service...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(user_router, prefix=settings.API_PREFIX)
app.include_router(job_router, prefix=settings.API_PREFIX)
app.include_router(log_router, prefix=settings.API_PREFIX)
app.include_router(report_router, prefix=settings.API_PREFIX)
app.include_router(system_router, prefix=settings.API_PREFIX)
app.include_router(fs_router, prefix=settings.API_PREFIX)

# WebSocket endpoint for real-time progress & status
@app.websocket("/ws/jobs")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for ping/client messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Sync Tool API is running. UI static files not built yet."}
