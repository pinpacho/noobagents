"""Input-validation helpers for the API layer."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

from src.config import get_settings


async def validate_upload(file: UploadFile | None) -> UploadFile | None:
    """Validate an optional file upload (MIME type, size)."""
    if file is None:
        return None

    settings = get_settings()

    # Check MIME type
    mime = file.content_type or "application/octet-stream"
    if mime not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{mime}' is not allowed. Accepted: {settings.allowed_mime_types}",
        )

    # Check size (read into memory — fine for ≤10 MB)
    contents = await file.read()
    if len(contents) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(contents)} bytes). Max: {settings.max_upload_size_bytes} bytes.",
        )
    # Reset the file pointer so the caller can read again
    await file.seek(0)
    return file
