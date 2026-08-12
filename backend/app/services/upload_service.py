import os
import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import get_settings


class UploadService:
    def __init__(self):
        self.settings = get_settings()
        Path(self.settings.upload_dir).mkdir(parents=True, exist_ok=True)

    async def save_file(self, file: UploadFile) -> str:
        content_type = (file.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image files are supported")

        suffix = Path(file.filename or "").suffix.lower()
        if not suffix or suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".svg", ".ico", ".tif", ".tiff"}:
            suffix = mimetypes.guess_extension(content_type) or ".img"
        name = f"{uuid.uuid4().hex}{suffix}"
        path = Path(self.settings.upload_dir) / name
        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)
        return f"/uploads/{name}"
