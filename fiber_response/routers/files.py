"""
@file: files.py
@author: Samuel Stolarik
@description:
    FastAPI router for
    experiment .pkl file
    listing and uploading
"""

from fastapi import (
    APIRouter, Depends, UploadFile, File,
    HTTPException, status
)
from typing import Annotated
import shutil
import os
from pathlib import Path

from fiber_response.dependencies import Settings, get_settings

router = APIRouter(
    prefix="/io",
    tags=["IO"]
)

@router.get("/files")
async def get_experiment_files(
    settings: Annotated[Settings, Depends(get_settings)]
):
    files = settings.data_dir.glob("*.pkl")

    return {
        "data_dir": settings.data_dir.resolve(),
        "files": files
    }

@router.post("/upload",
             status_code=status.HTTP_201_CREATED,
             responses={
                 status.HTTP_409_CONFLICT: {"description": "File already exits"}
             }
)
def upload_files(
    files: Annotated[list[UploadFile], File(description="Multiple files")],
    settings: Annotated[Settings, Depends(get_settings)]
):
    ddir = settings.data_dir.resolve()

    # Sanitize names and check uniqueness
    names = [Path(f.filename or "").name for f in files]
    if not all(names):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")
    if len(set(names)) != len(names):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Duplicate filenames in upload"
        )

    # Check filename uniqueness
    for fname in names:
        if (ddir / fname).exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File {ddir / fname} already exists."
            )

    # Save files on disk
    for file, fname in zip(files, names):
        with open(ddir / fname, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # On success return filenames
    return {"filenames": [file.filename for file in files]}

@router.delete("/file")
def delete_files(
    filename: str,
    settings: Annotated[Settings, Depends(get_settings)]
):
    ddir = settings.data_dir.resolve()
    if not (ddir/filename).exists():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "File does not exist"
        )

    os.remove(ddir/filename)
