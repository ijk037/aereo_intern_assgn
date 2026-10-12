import logging
import re
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLargeException, InvalidFileFormatException

logger = logging.getLogger(__name__)


class StorageService:
    """
    Handles saving uploaded files, enforcing file extension constraints,
    security sanitization, and size limits.
    """

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        # Remove paths and keep only base name with safe characters
        base_name = Path(filename).name
        sanitized = re.sub(r"[^\w\.\-\_]", "_", base_name)
        return sanitized or "upload_file"

    @classmethod
    async def save_upload(cls, upload_file: UploadFile) -> Tuple[str, Path, int]:
        original_name = upload_file.filename or "unknown"
        ext = Path(original_name).suffix.lower()

        if ext not in settings.ALLOWED_EXTENSIONS:
            raise InvalidFileFormatException(
                f"Unsupported file extension '{ext}'. Only {', '.join(settings.ALLOWED_EXTENSIONS)} are supported."
            )

        file_id = uuid.uuid4().hex[:12]
        sanitized_name = cls.sanitize_filename(original_name)
        saved_filename = f"{file_id}_{sanitized_name}"
        saved_path = settings.UPLOAD_DIR / saved_filename

        total_bytes = 0
        chunk_size = 1024 * 1024  # 1 MB chunk

        with open(saved_path, "wb") as f:
            while chunk := await upload_file.read(chunk_size):
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
                    # Clean up file and raise
                    saved_path.unlink(missing_ok=True)
                    raise FileTooLargeException(settings.MAX_UPLOAD_SIZE_BYTES)
                f.write(chunk)

        logger.info(
            "Saved uploaded file '%s' as '%s' (%d bytes)",
            original_name,
            saved_path,
            total_bytes,
        )
        return file_id, saved_path, total_bytes
