"""File storage for incident attachments."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from src.config import get_settings


async def save_upload(file: UploadFile) -> tuple[str, str]:
    """Persist an uploaded file to disk.

    Returns (saved_path, mime_type).
    """
    settings = get_settings()
    upload_dir = settings.upload_path

    suffix = Path(file.filename or "upload").suffix
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = upload_dir / filename

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    mime = file.content_type or "application/octet-stream"
    return str(dest), mime
