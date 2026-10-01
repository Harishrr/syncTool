import os
import time
from pathlib import Path
from typing import Callable, Optional
import paramiko
from app.engines.base import BaseTransferEngine

class SFTPEngine(BaseTransferEngine):
    def __init__(
        self,
        job_id: int,
        source: str,
        destination: str,
        host: str,
        port: int = 22,
        username: str = "",
        password: str = "",
        overwrite_mode: str = "newer",
        progress_callback: Optional[Callable[[float, str, float, int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        super().__init__(job_id, source, destination, progress_callback, log_callback)
        self.host = host
        self.port = port or 22
        self.username = username
        self.password = password
        self.overwrite_mode = overwrite_mode or "newer"
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.sftp_client: Optional[paramiko.SFTPClient] = None

    def run(self) -> dict:
        self.is_running = True
        self.is_paused = False
        self.is_stopped = False
        self._pause_event.set()

        src_path = Path(self.source)
        if not src_path.exists():
            self.is_running = False
            return {
                "status": "failed",
                "exit_code": -1,
                "bytes": 0,
                "files": 0,
                "log": f"Local source path does not exist: {self.source}",
                "error": f"Source path not found: {self.source}"
            }

        self.log(f"Connecting to SFTP server {self.host}:{self.port} as {self.username} (Overwrite mode: {self.overwrite_mode})...")
        
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                banner_timeout=10
            )
            self.sftp_client = self.ssh_client.open_sftp()
            self.log(f"SFTP connection established to {self.host}.")

            # Scan source items
            files_to_transfer = []
            total_bytes = 0
            if src_path.is_file():
                size = src_path.stat().st_size
                files_to_transfer.append((src_path, self.destination))
                total_bytes += size
            else:
                for root, _, files in os.walk(src_path):
                    for f in files:
                        full_local = Path(root) / f
                        rel_path = full_local.relative_to(src_path)
                        remote_dest = (Path(self.destination) / rel_path).as_posix()
                        size = full_local.stat().st_size
                        files_to_transfer.append((full_local, remote_dest))
                        total_bytes += size

            total_files = len(files_to_transfer)
            self.log(f"Starting SFTP transfer of {total_files} files ({total_bytes} bytes).")

            bytes_transferred_total = 0
            files_copied = 0
            start_time = time.time()

            for local_file, remote_file in files_to_transfer:
                if self.is_stopped:
                    break

                # Handle pause
                self._pause_event.wait()
                if self.is_stopped:
                    break

                # Ensure remote directory exists
                remote_dir = str(Path(remote_file).parent.as_posix())
                self._mkdir_p(remote_dir)

                file_size = local_file.stat().st_size

                # Check overwrite mode: if 'newer', compare timestamps
                if self.overwrite_mode == "newer":
                    try:
                        remote_stat = self.sftp_client.stat(remote_file)
                        local_mtime = local_file.stat().st_mtime
                        if remote_stat.st_mtime and remote_stat.st_mtime >= local_mtime and remote_stat.st_size == file_size:
                            # File is up to date, skip
                            self.log(f"Skipping {local_file.name}: Remote file is already up to date.")
                            bytes_transferred_total += file_size
                            files_copied += 1
                            pct = (bytes_transferred_total / max(1, total_bytes)) * 100.0
                            self.report_progress(
                                progress=round(min(99.9, pct), 1),
                                current_file=local_file.name,
                                speed_mbps=0.0,
                                bytes_copied=bytes_transferred_total,
                                total_bytes=total_bytes
                            )
                            continue
                    except (IOError, OSError):
                        # Remote file does not exist, proceed with upload
                        pass

                file_transferred = 0

                def file_callback(transferred, total):
                    nonlocal bytes_transferred_total, file_transferred
                    # Handle pause inside callback
                    self._pause_event.wait()
                    if self.is_stopped:
                        raise InterruptedError("Transfer stopped by user.")

                    delta = transferred - file_transferred
                    file_transferred = transferred
                    bytes_transferred_total += delta
                    
                    elapsed = max(0.1, time.time() - start_time)
                    speed = (bytes_transferred_total / (1024 * 1024)) / elapsed
                    pct = (bytes_transferred_total / max(1, total_bytes)) * 100.0
                    self.report_progress(
                        progress=round(min(99.9, pct), 1),
                        current_file=local_file.name,
                        speed_mbps=round(speed, 2),
                        bytes_copied=bytes_transferred_total,
                        total_bytes=total_bytes
                    )

                self.log(f"Uploading {local_file.name} to {remote_file}...")
                self.sftp_client.put(str(local_file), remote_file, callback=file_callback)
                files_copied += 1

            if self.is_stopped:
                return {
                    "status": "cancelled",
                    "exit_code": -1,
                    "bytes": bytes_transferred_total,
                    "files": files_copied,
                    "log": "SFTP transfer cancelled by user.",
                    "error": "Stopped by user"
                }

            self.report_progress(100.0, "Complete", 0.0, total_bytes, total_bytes)
            self.log(f"SFTP transfer completed successfully: {files_copied} files, {total_bytes} bytes.")
            return {
                "status": "success",
                "exit_code": 0,
                "bytes": total_bytes,
                "files": files_copied,
                "log": f"SFTP transferred {files_copied} files successfully.",
                "error": None
            }

        except InterruptedError:
            return {
                "status": "cancelled",
                "exit_code": -1,
                "bytes": bytes_transferred_total,
                "files": files_copied,
                "log": "Transfer stopped.",
                "error": "Stopped by user"
            }
        except Exception as e:
            self.log(f"SFTP Error: {e}")
            return {
                "status": "failed",
                "exit_code": -1,
                "bytes": 0,
                "files": 0,
                "log": f"SFTP Failed: {e}",
                "error": str(e)
            }
        finally:
            self.is_running = False
            if self.sftp_client:
                try:
                    self.sftp_client.close()
                except Exception:
                    pass
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                except Exception:
                    pass

    def _mkdir_p(self, remote_dir: str):
        if not self.sftp_client or remote_dir in ("", ".", "/"):
            return
        dirs = []
        current = remote_dir
        while current and current not in ("/", "."):
            dirs.append(current)
            current = str(Path(current).parent.as_posix())
        dirs.reverse()
        for d in dirs:
            try:
                self.sftp_client.stat(d)
            except IOError:
                try:
                    self.sftp_client.mkdir(d)
                except Exception:
                    pass

    def pause(self) -> bool:
        if not self.is_running or self.is_paused:
            return False
        self.is_paused = True
        self._pause_event.clear()
        self.log(f"SFTP Job {self.job_id} paused.")
        return True

    def resume(self) -> bool:
        if not self.is_running or not self.is_paused:
            return False
        self.is_paused = False
        self._pause_event.set()
        self.log(f"SFTP Job {self.job_id} resumed.")
        return True

    def stop(self) -> bool:
        if not self.is_running:
            return False
        self.is_stopped = True
        self.is_paused = False
        self._pause_event.set()  # unblock if paused so loop can terminate
        self.log(f"SFTP Job {self.job_id} stop requested.")
        return True
