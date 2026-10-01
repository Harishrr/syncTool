import os
import socket
import time
import struct
from pathlib import Path
from typing import Callable, Optional
from app.engines.base import BaseTransferEngine

CHUNK_SIZE = 1400  # MTU friendly packet payload

class UDPEngine(BaseTransferEngine):
    def __init__(
        self,
        job_id: int,
        source: str,
        destination: str,
        host: str,
        port: int = 9999,
        overwrite_mode: str = "newer",
        progress_callback: Optional[Callable[[float, str, float, int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        super().__init__(job_id, source, destination, progress_callback, log_callback)
        self.host = host or "127.0.0.1"
        self.port = port or 9999
        self.overwrite_mode = overwrite_mode or "newer"
        self.sock: Optional[socket.socket] = None

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

        self.log(f"Initializing UDP file streamer to {self.host}:{self.port}...")
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5.0)

            # Discover files
            files_to_send = []
            total_bytes = 0
            if src_path.is_file():
                files_to_send.append(src_path)
                total_bytes += src_path.stat().st_size
            else:
                for root, _, files in os.walk(src_path):
                    for f in files:
                        p = Path(root) / f
                        files_to_send.append(p)
                        total_bytes += p.stat().st_size

            total_files = len(files_to_send)
            self.log(f"Broadcasting {total_files} files ({total_bytes} bytes) via UDP...")

            total_bytes_sent = 0
            files_sent = 0
            start_time = time.time()

            for file_path in files_to_send:
                if self.is_stopped:
                    break

                self._pause_event.wait()
                if self.is_stopped:
                    break

                file_size = file_path.stat().st_size
                rel_path = file_path.relative_to(src_path) if src_path.is_dir() else file_path.name
                rel_path_str = str(rel_path).replace("\\", "/")
                
                # Send File Header Packet: Type 0x01, filename_len (2B), filesize (8B), filename
                header_data = rel_path_str.encode("utf-8")
                header_pkt = struct.pack("!BIQ", 1, len(header_data), file_size) + header_data
                self.sock.sendto(header_pkt, (self.host, self.port))

                with open(file_path, "rb") as f:
                    seq = 0
                    while True:
                        if self.is_stopped:
                            break
                        self._pause_event.wait()

                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        # Data Packet: Type 0x02, SeqNum (4B), Data
                        data_pkt = struct.pack("!BI", 2, seq) + chunk
                        self.sock.sendto(data_pkt, (self.host, self.port))
                        seq += 1

                        total_bytes_sent += len(chunk)
                        elapsed = max(0.1, time.time() - start_time)
                        speed = (total_bytes_sent / (1024 * 1024)) / elapsed
                        pct = (total_bytes_sent / max(1, total_bytes)) * 100.0

                        self.report_progress(
                            progress=round(min(99.9, pct), 1),
                            current_file=file_path.name,
                            speed_mbps=round(speed, 2),
                            bytes_copied=total_bytes_sent,
                            total_bytes=total_bytes
                        )
                        # Micro pacing to prevent buffer overflow on sender
                        time.sleep(0.0005)

                # Send File End Packet: Type 0x03
                eof_pkt = struct.pack("!BI", 3, seq)
                self.sock.sendto(eof_pkt, (self.host, self.port))
                files_sent += 1

            if self.is_stopped:
                return {
                    "status": "cancelled",
                    "exit_code": -1,
                    "bytes": total_bytes_sent,
                    "files": files_sent,
                    "log": "UDP transfer cancelled by user.",
                    "error": "Stopped by user"
                }

            self.report_progress(100.0, "Complete", 0.0, total_bytes, total_bytes)
            self.log(f"UDP transfer complete: {files_sent} files sent.")
            return {
                "status": "success",
                "exit_code": 0,
                "bytes": total_bytes_sent,
                "files": files_sent,
                "log": f"UDP transferred {files_sent} files successfully.",
                "error": None
            }

        except Exception as e:
            self.log(f"UDP Error: {e}")
            return {
                "status": "failed",
                "exit_code": -1,
                "bytes": 0,
                "files": 0,
                "log": f"UDP transmission failed: {e}",
                "error": str(e)
            }
        finally:
            self.is_running = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass

    def pause(self) -> bool:
        if not self.is_running or self.is_paused:
            return False
        self.is_paused = True
        self._pause_event.clear()
        self.log(f"UDP Job {self.job_id} paused.")
        return True

    def resume(self) -> bool:
        if not self.is_running or not self.is_paused:
            return False
        self.is_paused = False
        self._pause_event.set()
        self.log(f"UDP Job {self.job_id} resumed.")
        return True

    def stop(self) -> bool:
        if not self.is_running:
            return False
        self.is_stopped = True
        self.is_paused = False
        self._pause_event.set()
        self.log(f"UDP Job {self.job_id} stopped.")
        return True
