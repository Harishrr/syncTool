import subprocess
import os
import re
import time
import psutil
from pathlib import Path
from typing import Callable, Optional
from app.engines.base import BaseTransferEngine

class RobocopyEngine(BaseTransferEngine):
    def __init__(
        self,
        job_id: int,
        source: str,
        destination: str,
        overwrite_mode: str = "newer",
        progress_callback: Optional[Callable[[float, str, float, int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        super().__init__(job_id, source, destination, progress_callback, log_callback)
        self.overwrite_mode = overwrite_mode or "newer"
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.total_bytes = 0
        self.total_files = 0

    def _calculate_source_stats(self):
        try:
            p = Path(self.source)
            if p.is_file():
                self.total_bytes = p.stat().st_size
                self.total_files = 1
            elif p.is_dir():
                total_b = 0
                total_f = 0
                for item in p.rglob("*"):
                    if item.is_file():
                        total_f += 1
                        try:
                            total_b += item.stat().st_size
                        except Exception:
                            pass
                self.total_bytes = total_b
                self.total_files = total_f
        except Exception as e:
            self.log(f"Warning calculating source stats: {e}")

    def run(self) -> dict:
        self.is_running = True
        self.is_stopped = False
        self.is_paused = False
        
        # Ensure destination directory exists if source is directory
        src_path = Path(self.source)
        dst_path = Path(self.destination)
        
        if not src_path.exists():
            self.is_running = False
            return {
                "status": "failed",
                "exit_code": -1,
                "bytes": 0,
                "files": 0,
                "log": f"Source path does not exist: {self.source}",
                "error": f"Source path not found: {self.source}"
            }
            
        try:
            dst_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.is_running = False
            return {
                "status": "failed",
                "exit_code": -1,
                "bytes": 0,
                "files": 0,
                "log": f"Failed to create destination directory: {e}",
                "error": str(e)
            }

        self.log(f"Calculating source statistics for {self.source}...")
        self._calculate_source_stats()
        self.log(f"Found {self.total_files} files ({self.total_bytes} bytes) to sync.")
        
        # Build Robocopy command
        # /E: subdirectories including empty
        # /BYTES: print sizes in bytes
        # /NP: don't display % in noisy form (or we parse it)
        # /R:2 /W:2: 2 retries, 2 sec wait
        # /TEE: output to console
        # /XO: Exclude older files (overwrite only if source is newer)
        # /IS: Include same files (always overwrite)
        cmd = [
            "robocopy",
            str(src_path),
            str(dst_path),
            "/E",
            "/BYTES",
            "/R:2",
            "/W:2"
        ]
        
        if self.overwrite_mode == "newer":
            cmd.append("/XO")  # Exclude older files (only newer files overwrite destination)
            self.log("Overwrite mode: Only newer files will overwrite destination (/XO)")
        else:
            cmd.append("/IS")  # Force unconditional overwrite including same files
            self.log("Overwrite mode: Always overwrite all matching destination files (/IS)")
        
        self.log(f"Executing: {' '.join(cmd)}")
        full_log = []
        copied_bytes = 0
        copied_files = 0
        start_time = time.time()
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            self.pid = self.process.pid
            
            # Progress regex patterns
            # Robocopy output lines typically include file sizes and names
            pct_regex = re.compile(r"(\d+(?:\.\d+)?)%")
            
            last_report_time = time.time()
            
            while True:
                if self.is_stopped:
                    break
                    
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                    
                if line:
                    clean_line = line.strip()
                    if clean_line:
                        full_log.append(clean_line)
                        
                    # Check for percentage output
                    pct_match = pct_regex.search(line)
                    if pct_match:
                        try:
                            pct = float(pct_match.group(1))
                            elapsed = max(0.1, time.time() - start_time)
                            est_bytes = int((pct / 100.0) * self.total_bytes) if self.total_bytes > 0 else 0
                            speed = (est_bytes / (1024 * 1024)) / elapsed
                            self.report_progress(
                                progress=min(100.0, pct),
                                current_file="",
                                speed_mbps=round(speed, 2),
                                bytes_copied=est_bytes,
                                total_bytes=self.total_bytes
                            )
                        except Exception:
                            pass
                    elif "New File" in line or "100%" in line:
                        copied_files += 1
                        if self.total_files > 0:
                            pct = min(99.0, (copied_files / self.total_files) * 100.0)
                            elapsed = max(0.1, time.time() - start_time)
                            speed = ((copied_files * (self.total_bytes / max(1, self.total_files))) / (1024 * 1024)) / elapsed
                            self.report_progress(
                                progress=round(pct, 1),
                                current_file=clean_line[:60],
                                speed_mbps=round(speed, 2),
                                bytes_copied=int((pct/100.0)*self.total_bytes),
                                total_bytes=self.total_bytes
                            )

            if self.is_stopped:
                return {
                    "status": "cancelled",
                    "exit_code": -1,
                    "bytes": copied_bytes,
                    "files": copied_files,
                    "log": "\n".join(full_log[-50:]),
                    "error": "Job was stopped by user."
                }

            exit_code = self.process.wait()
            self.is_running = False
            
            # Robocopy exit code <= 7 indicates success (0=no files copied, 1=copied, 2=extra, etc.)
            is_success = exit_code <= 7
            status = "success" if is_success else "failed"
            
            if is_success:
                self.report_progress(
                    progress=100.0,
                    current_file="Completed",
                    speed_mbps=0.0,
                    bytes_copied=self.total_bytes,
                    total_bytes=self.total_bytes
                )
            
            error_msg = None if is_success else f"Robocopy failed with exit code {exit_code}"
            
            return {
                "status": status,
                "exit_code": exit_code,
                "bytes": self.total_bytes if is_success else copied_bytes,
                "files": self.total_files if is_success else copied_files,
                "log": "\n".join(full_log[-50:]),
                "error": error_msg
            }
            
        except Exception as e:
            self.is_running = False
            self.log(f"Exception during robocopy: {e}")
            return {
                "status": "failed",
                "exit_code": -1,
                "bytes": copied_bytes,
                "files": copied_files,
                "log": "\n".join(full_log[-30:]),
                "error": str(e)
            }

    def pause(self) -> bool:
        if not self.is_running or self.is_paused or not self.pid:
            return False
        try:
            p = psutil.Process(self.pid)
            p.suspend()
            self.is_paused = True
            self.log(f"Job {self.job_id} (PID {self.pid}) suspended/paused.")
            return True
        except Exception as e:
            self.log(f"Failed to pause job {self.job_id}: {e}")
            return False

    def resume(self) -> bool:
        if not self.is_running or not self.is_paused or not self.pid:
            return False
        try:
            p = psutil.Process(self.pid)
            p.resume()
            self.is_paused = False
            self.log(f"Job {self.job_id} (PID {self.pid}) resumed.")
            return True
        except Exception as e:
            self.log(f"Failed to resume job {self.job_id}: {e}")
            return False

    def stop(self) -> bool:
        if not self.is_running or not self.pid:
            return False
        try:
            self.is_stopped = True
            p = psutil.Process(self.pid)
            # If suspended, resume first so it can handle termination cleanly
            if self.is_paused:
                p.resume()
            p.terminate()
            time.sleep(0.2)
            if p.is_running():
                p.kill()
            self.is_running = False
            self.log(f"Job {self.job_id} (PID {self.pid}) stopped.")
            return True
        except Exception as e:
            self.log(f"Failed to stop job {self.job_id}: {e}")
            return False
