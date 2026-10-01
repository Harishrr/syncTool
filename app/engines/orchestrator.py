import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Set, Optional, List
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Job, JobRun, SystemLog
from app.engines.base import BaseTransferEngine
from app.engines.robocopy import RobocopyEngine
from app.engines.sftp import SFTPEngine
from app.engines.udp import UDPEngine

class ConnectionManager:
    """Manages active WebSocket connections to stream real-time job updates."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        dead_connections = set()
        for conn in list(self.active_connections):
            try:
                await conn.send_json(message)
            except Exception:
                dead_connections.add(conn)
        for dead in dead_connections:
            self.active_connections.discard(dead)

    def broadcast_threadsafe(self, message: dict):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

ws_manager = ConnectionManager()

class JobOrchestrator:
    def __init__(self):
        self.active_engines: Dict[int, BaseTransferEngine] = {}
        self.lock = threading.Lock()

    def _get_db(self) -> Session:
        return SessionLocal()

    def _log_system_event(self, level: str, category: str, action: str, details: str, user_id: Optional[int] = None):
        try:
            db = self._get_db()
            sys_log = SystemLog(
                level=level,
                category=category,
                action=action,
                details=details,
                user_id=user_id
            )
            db.add(sys_log)
            db.commit()
            db.close()
        except Exception:
            pass

    def start_job(self, job_id: int, user_id: Optional[int] = None) -> bool:
        with self.lock:
            if job_id in self.active_engines and self.active_engines[job_id].is_running:
                # If paused, resume it
                if self.active_engines[job_id].is_paused:
                    return self.resume_job(job_id)
                return False

            db = self._get_db()
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                db.close()
                return False

            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.error_message = None
            job.progress = 0.0
            db.commit()

            # Instantiate transfer engine based on job transfer_type
            engine: BaseTransferEngine
            overwrite_mode = getattr(job, "overwrite_mode", "newer") or "newer"
            if job.transfer_type == "robocopy":
                engine = RobocopyEngine(
                    job_id=job.id,
                    source=job.source_path,
                    destination=job.dest_path,
                    overwrite_mode=overwrite_mode,
                    progress_callback=lambda p, cf, s, bc, tb: self._handle_progress(job_id, p, cf, s, bc, tb),
                    log_callback=lambda msg: self._log_engine_msg(job_id, msg)
                )
            elif job.transfer_type == "sftp":
                engine = SFTPEngine(
                    job_id=job.id,
                    source=job.source_path,
                    destination=job.dest_path,
                    host=job.host or "127.0.0.1",
                    port=job.port or 22,
                    username=job.remote_username or "",
                    password=job.remote_password or "",
                    overwrite_mode=overwrite_mode,
                    progress_callback=lambda p, cf, s, bc, tb: self._handle_progress(job_id, p, cf, s, bc, tb),
                    log_callback=lambda msg: self._log_engine_msg(job_id, msg)
                )
            elif job.transfer_type == "udp":
                engine = UDPEngine(
                    job_id=job.id,
                    source=job.source_path,
                    destination=job.dest_path,
                    host=job.host or "127.0.0.1",
                    port=job.port or 9999,
                    overwrite_mode=overwrite_mode,
                    progress_callback=lambda p, cf, s, bc, tb: self._handle_progress(job_id, p, cf, s, bc, tb),
                    log_callback=lambda msg: self._log_engine_msg(job_id, msg)
                )
            else:
                db.close()
                return False

            self.active_engines[job_id] = engine
            db.close()

            # Start worker thread
            worker_thread = threading.Thread(
                target=self._run_engine_worker,
                args=(job_id, engine, user_id),
                daemon=True
            )
            worker_thread.start()

            ws_manager.broadcast_threadsafe({
                "type": "job_status",
                "job_id": job_id,
                "status": "running"
            })
            self._log_system_event("INFO", "JOB", "JOB_STARTED", f"Job '{job.name}' (ID: {job_id}) started via {job.transfer_type}.", user_id)
            return True

    def _handle_progress(self, job_id: int, progress: float, current_file: str, speed_mbps: float, bytes_copied: int, total_bytes: int):
        # Broadcast immediately to UI
        ws_manager.broadcast_threadsafe({
            "type": "job_progress",
            "job_id": job_id,
            "progress": round(progress, 1),
            "current_file": current_file,
            "speed_mbps": speed_mbps,
            "bytes_copied": bytes_copied,
            "total_bytes": total_bytes
        })

    def _log_engine_msg(self, job_id: int, msg: str):
        # Can be forwarded to logs or UI log panel
        pass

    def _run_engine_worker(self, job_id: int, engine: BaseTransferEngine, user_id: Optional[int]):
        start_time = datetime.now(timezone.utc)
        result = engine.run()
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        status = result.get("status", "failed")
        final_db_status = "completed" if status == "success" else ("cancelled" if status == "cancelled" else "failed")

        db = self._get_db()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = final_db_status
            job.finished_at = end_time
            job.progress = 100.0 if final_db_status == "completed" else job.progress
            job.bytes_copied = result.get("bytes", 0)
            job.error_message = result.get("error")
            
            # Record JobRun history
            run_history = JobRun(
                job_id=job.id,
                user_id=user_id or job.created_by_id,
                status=final_db_status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=round(duration, 2),
                bytes_transferred=result.get("bytes", 0),
                files_copied=result.get("files", 0),
                exit_code=result.get("exit_code", 0),
                log_output=result.get("log")
            )
            db.add(run_history)
            db.commit()

        db.close()

        with self.lock:
            if job_id in self.active_engines:
                del self.active_engines[job_id]

        ws_manager.broadcast_threadsafe({
            "type": "job_status",
            "job_id": job_id,
            "status": final_db_status,
            "progress": 100.0 if final_db_status == "completed" else 0.0,
            "error": result.get("error")
        })

        log_level = "INFO" if final_db_status == "completed" else "ERROR"
        self._log_system_event(
            log_level,
            "JOB",
            f"JOB_{final_db_status.upper()}",
            f"Job {job_id} finished with status '{final_db_status}'. Copied {result.get('files', 0)} files ({result.get('bytes', 0)} bytes).",
            user_id
        )

    def pause_job(self, job_id: int) -> bool:
        with self.lock:
            engine = self.active_engines.get(job_id)
            if not engine:
                return False
            success = engine.pause()
            if success:
                db = self._get_db()
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = "paused"
                    db.commit()
                db.close()
                ws_manager.broadcast_threadsafe({
                    "type": "job_status",
                    "job_id": job_id,
                    "status": "paused"
                })
                self._log_system_event("INFO", "JOB", "JOB_PAUSED", f"Job {job_id} paused.")
            return success

    def resume_job(self, job_id: int) -> bool:
        with self.lock:
            engine = self.active_engines.get(job_id)
            if not engine:
                return False
            success = engine.resume()
            if success:
                db = self._get_db()
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = "running"
                    db.commit()
                db.close()
                ws_manager.broadcast_threadsafe({
                    "type": "job_status",
                    "job_id": job_id,
                    "status": "running"
                })
                self._log_system_event("INFO", "JOB", "JOB_RESUMED", f"Job {job_id} resumed.")
            return success

    def stop_job(self, job_id: int) -> bool:
        with self.lock:
            engine = self.active_engines.get(job_id)
            if not engine:
                # Still set status in DB to cancelled if it was pending
                db = self._get_db()
                job = db.query(Job).filter(Job.id == job_id).first()
                if job and job.status in ("pending", "running", "paused"):
                    job.status = "cancelled"
                    db.commit()
                db.close()
                ws_manager.broadcast_threadsafe({
                    "type": "job_status",
                    "job_id": job_id,
                    "status": "cancelled"
                })
                return True
            success = engine.stop()
            if success:
                db = self._get_db()
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = "cancelled"
                    db.commit()
                db.close()
                ws_manager.broadcast_threadsafe({
                    "type": "job_status",
                    "job_id": job_id,
                    "status": "cancelled"
                })
                self._log_system_event("WARNING", "JOB", "JOB_STOPPED", f"Job {job_id} cancelled by user.")
            return success

    def start_all_jobs(self, user_id: Optional[int] = None) -> List[int]:
        db = self._get_db()
        jobs = db.query(Job).filter(Job.status.in_(["pending", "paused", "failed", "cancelled"])).all()
        job_ids = [j.id for j in jobs]
        db.close()

        started = []
        for jid in job_ids:
            if self.start_job(jid, user_id):
                started.append(jid)
        return started

    def pause_all_jobs(self) -> List[int]:
        with self.lock:
            running_ids = [jid for jid, eng in self.active_engines.items() if eng.is_running and not eng.is_paused]
        
        paused = []
        for jid in running_ids:
            if self.pause_job(jid):
                paused.append(jid)
        return paused

    def resume_all_jobs(self) -> List[int]:
        with self.lock:
            paused_ids = [jid for jid, eng in self.active_engines.items() if eng.is_running and eng.is_paused]

        resumed = []
        for jid in paused_ids:
            if self.resume_job(jid):
                resumed.append(jid)
        return resumed

    def stop_all_jobs(self) -> List[int]:
        with self.lock:
            active_ids = list(self.active_engines.keys())

        stopped = []
        for jid in active_ids:
            if self.stop_job(jid):
                stopped.append(jid)
        return stopped

orchestrator = JobOrchestrator()
