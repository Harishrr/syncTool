import os
import sys
import string
import stat
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import paramiko
from app.services.log_service import logger

def get_system_drives() -> List[Dict[str, str]]:
    """Detect available drives on Windows or root on Unix."""
    drives = []
    if sys.platform == "win32":
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                drives.append({
                    "name": f"Local Disk ({letter}:)",
                    "path": drive_path,
                    "letter": letter
                })
    else:
        drives.append({
            "name": "Root (/)",
            "path": "/",
            "letter": "/"
        })
    return drives

def get_system_shortcuts() -> List[Dict[str, str]]:
    """Get common directory shortcuts for quick access."""
    shortcuts = []
    home = Path.home()
    
    shortcuts.append({"name": "Home Directory", "path": str(home), "icon": "fa-house"})
    
    desktop = home / "Desktop"
    if desktop.exists():
        shortcuts.append({"name": "Desktop", "path": str(desktop), "icon": "fa-desktop"})
        
    documents = home / "Documents"
    if documents.exists():
        shortcuts.append({"name": "Documents", "path": str(documents), "icon": "fa-folder"})
        
    downloads = home / "Downloads"
    if downloads.exists():
        shortcuts.append({"name": "Downloads", "path": str(downloads), "icon": "fa-download"})
        
    cwd = Path.cwd()
    shortcuts.append({"name": "Sync Tool Workspace", "path": str(cwd), "icon": "fa-briefcase"})
    
    return shortcuts

def browse_local(path: Optional[str] = None, show_files: bool = True) -> Dict[str, Any]:
    """Browse the local filesystem and return directories, files, and navigation context."""
    drives = get_system_drives()
    shortcuts = get_system_shortcuts()

    # Determine default starting path if none provided or invalid
    if not path or not path.strip():
        # Start at user home or first available drive
        default_target = Path.home()
        if not default_target.exists() and drives:
            default_target = Path(drives[0]["path"])
        path = str(default_target)

    target_path = Path(path).resolve()
    if not target_path.exists():
        # If path does not exist, try parent or home
        if target_path.parent.exists():
            target_path = target_path.parent
        else:
            target_path = Path.home()

    # Determine parent path
    parent_path: Optional[str] = None
    if target_path.parent != target_path:
        parent_path = str(target_path.parent)

    items = []
    error_msg = None

    try:
        with os.scandir(str(target_path)) as entries:
            for entry in entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    if not show_files and not is_dir:
                        continue

                    entry_stat = entry.stat(follow_symlinks=False)
                    mod_time = datetime.fromtimestamp(entry_stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    
                    extension = ""
                    if not is_dir and "." in entry.name:
                        extension = Path(entry.name).suffix.lower()

                    items.append({
                        "name": entry.name,
                        "path": str(Path(entry.path)),
                        "is_dir": is_dir,
                        "size": entry_stat.st_size if not is_dir else None,
                        "modified": mod_time,
                        "extension": extension
                    })
                except (PermissionError, OSError):
                    # Skip items that cannot be accessed
                    continue
    except PermissionError:
        error_msg = f"Access denied to folder: {target_path}"
    except Exception as e:
        error_msg = f"Error reading folder: {str(e)}"

    # Sort: folders first (alphabetical), then files (alphabetical)
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    return {
        "current_path": str(target_path),
        "parent_path": parent_path,
        "drives": drives,
        "shortcuts": shortcuts,
        "items": items,
        "error": error_msg
    }

def create_local_directory(parent_path: str, folder_name: str) -> Dict[str, Any]:
    """Create a new directory in the specified parent folder."""
    clean_name = folder_name.strip()
    if not clean_name:
        raise ValueError("Folder name cannot be empty")
    
    # Prohibit directory traversal in the name
    if any(c in clean_name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        raise ValueError("Folder name contains invalid characters")

    parent = Path(parent_path).resolve()
    if not parent.exists() or not parent.is_dir():
        raise ValueError(f"Parent directory does not exist: {parent_path}")

    new_dir = parent / clean_name
    if new_dir.exists():
        raise ValueError(f"A folder or file named '{clean_name}' already exists")

    new_dir.mkdir(parents=False, exist_ok=False)
    return {
        "success": True,
        "new_path": str(new_dir),
        "folder_name": clean_name
    }

def open_native_picker(mode: str = "directory", initial_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Open native Windows / OS file or folder picker using tkinter.
    Runs synchronously in request thread (ideal for local desktop/web runs).
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        init_dir = initial_path if initial_path and os.path.exists(initial_path) else str(Path.home())
        
        if mode == "file":
            selected = filedialog.askopenfilename(
                title="Select Source / Destination File",
                initialdir=init_dir
            )
        else:
            selected = filedialog.askdirectory(
                title="Select Source / Destination Folder",
                initialdir=init_dir
            )
            
        root.destroy()
        
        if selected:
            # Normalize path for Windows if applicable
            norm_selected = os.path.normpath(selected)
            return {"selected_path": norm_selected, "cancelled": False}
        return {"selected_path": None, "cancelled": True}
    except Exception as e:
        logger.warning(f"Native picker could not open: {e}")
        return {"selected_path": None, "cancelled": True, "error": str(e)}

def browse_sftp(
    host: str,
    port: int = 22,
    username: str = "",
    password: Optional[str] = None,
    remote_path: Optional[str] = None,
    show_files: bool = True
) -> Dict[str, Any]:
    """Connect to a remote SFTP host and list directory contents."""
    if not host or not host.strip():
        raise ValueError("SFTP Host is required to browse remote server")
    if not username or not username.strip():
        raise ValueError("SFTP Username is required to browse remote server")

    port = port or 22
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=host.strip(),
            port=int(port),
            username=username.strip(),
            password=password or "",
            timeout=8,
            banner_timeout=8
        )
        sftp = ssh.open_sftp()

        # Resolve remote target path
        if not remote_path or not remote_path.strip():
            try:
                curr = sftp.normalize('.')
            except Exception:
                curr = "/"
        else:
            curr = remote_path.strip()

        # Normalize path slashes
        curr = curr.replace("\\", "/")
        if not curr.startswith("/"):
            curr = "/" + curr

        # Determine parent path
        parent_path = None
        if curr not in ("/", ""):
            parent = str(Path(curr).parent.as_posix())
            parent_path = parent if parent else "/"

        items = []
        try:
            file_attrs = sftp.listdir_attr(curr)
            for attr in file_attrs:
                is_dir = stat.S_ISDIR(attr.st_mode)
                if not show_files and not is_dir:
                    continue

                full_item_path = f"{curr.rstrip('/')}/{attr.filename}"
                mod_time = datetime.fromtimestamp(attr.st_mtime).strftime("%Y-%m-%d %H:%M") if attr.st_mtime else None
                ext = Path(attr.filename).suffix.lower() if not is_dir and "." in attr.filename else ""

                items.append({
                    "name": attr.filename,
                    "path": full_item_path,
                    "is_dir": is_dir,
                    "size": attr.st_size if not is_dir else None,
                    "modified": mod_time,
                    "extension": ext
                })
        except Exception as read_err:
            raise ValueError(f"Failed to read remote path '{curr}': {read_err}")

        # Sort: directories first, then files
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "current_path": curr,
            "parent_path": parent_path,
            "items": items,
            "host": host,
            "username": username
        }
    except Exception as e:
        raise ValueError(f"SFTP connection failed to {host}:{port}: {str(e)}")
    finally:
        try:
            ssh.close()
        except Exception:
            pass
