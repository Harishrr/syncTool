from abc import ABC, abstractmethod
from typing import Callable, Optional
import threading

class BaseTransferEngine(ABC):
    def __init__(
        self,
        job_id: int,
        source: str,
        destination: str,
        progress_callback: Optional[Callable[[float, str, float, int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        self.job_id = job_id
        self.source = source
        self.destination = destination
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        
        self.is_running = False
        self.is_paused = False
        self.is_stopped = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # set means NOT paused

    @abstractmethod
    def run(self) -> dict:
        """Executes the transfer. Returns a summary dictionary:
        {'status': 'success'|'failed'|'cancelled', 'exit_code': int, 'bytes': int, 'files': int, 'log': str, 'error': str}
        """
        pass

    @abstractmethod
    def pause(self) -> bool:
        """Pauses the transfer."""
        pass

    @abstractmethod
    def resume(self) -> bool:
        """Resumes the transfer."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stops the transfer immediately."""
        pass

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)

    def report_progress(self, progress: float, current_file: str = "", speed_mbps: float = 0.0, bytes_copied: int = 0, total_bytes: int = 0):
        if self.progress_callback:
            self.progress_callback(progress, current_file, speed_mbps, bytes_copied, total_bytes)
