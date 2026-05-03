"""File upload validation rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set, Tuple

MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024  # 250 MB

ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".xlsx", ".txt", ".csv"}

ALLOWED_CONTENT_TYPES: Set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
}


@dataclass
class ValidationResult:
    valid: bool
    error_title: Optional[str] = None
    error_detail: Optional[str] = None
    status_code: int = 200


def validate_upload(blob_name: str, size_bytes: int, content_type: Optional[str] = None) -> ValidationResult:
    """Validate a file upload against size and type constraints."""
    if size_bytes > MAX_FILE_SIZE_BYTES:
        return ValidationResult(
            valid=False,
            error_title="Request Entity Too Large",
            error_detail=f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
            status_code=413,
        )

    ext = _get_extension(blob_name)
    if ext not in ALLOWED_EXTENSIONS:
        return ValidationResult(
            valid=False,
            error_title="Unsupported Media Type",
            error_detail=f"File type '{ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
            status_code=415,
        )

    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        return ValidationResult(
            valid=False,
            error_title="Unsupported Media Type",
            error_detail=f"Content type '{content_type}' is not allowed.",
            status_code=415,
        )

    return ValidationResult(valid=True)


def _get_extension(filename: str) -> str:
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return ""
    return filename[dot_index:].lower()
