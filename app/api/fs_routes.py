from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.models import User
from app.auth.dependencies import get_current_user
from app.services import fs_service

router = APIRouter(prefix="/fs", tags=["Filesystem & Remote Browser"])

class MkdirRequest(BaseModel):
    parent_path: str = Field(..., min_length=1)
    folder_name: str = Field(..., min_length=1)

class NativePickerRequest(BaseModel):
    mode: str = Field(default="directory", pattern="^(directory|file)$")
    initial_path: Optional[str] = None

class SFTPBrowseRequest(BaseModel):
    host: str = Field(..., min_length=1)
    port: Optional[int] = 22
    username: str = Field(..., min_length=1)
    password: Optional[str] = None
    remote_path: Optional[str] = None
    show_files: Optional[bool] = True

@router.get("/local")
def browse_local_filesystem(
    path: Optional[str] = Query(None, description="Directory path to browse"),
    show_files: bool = Query(True, description="Whether to include files in listing"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """List contents of a local directory, available drives, and common shortcuts."""
    try:
        data = fs_service.browse_local(path=path, show_files=show_files)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to browse local path: {str(e)}")

@router.post("/mkdir")
def create_directory(
    payload: MkdirRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new folder in the specified local directory."""
    try:
        result = fs_service.create_local_directory(
            parent_path=payload.parent_path,
            folder_name=payload.folder_name
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create directory: {str(e)}")

@router.post("/native-picker")
def open_os_native_picker(
    payload: NativePickerRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Launch the host OS native folder or file dialog."""
    result = fs_service.open_native_picker(
        mode=payload.mode,
        initial_path=payload.initial_path
    )
    return result

@router.post("/sftp")
def browse_sftp_remote(
    payload: SFTPBrowseRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Connect to a remote SFTP server and list remote directories and files."""
    try:
        result = fs_service.browse_sftp(
            host=payload.host,
            port=payload.port or 22,
            username=payload.username,
            password=payload.password,
            remote_path=payload.remote_path,
            show_files=payload.show_files if payload.show_files is not None else True
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SFTP exploration error: {str(e)}")
