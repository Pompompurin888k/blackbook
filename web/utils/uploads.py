"""
Upload Utilities - shared portal file upload helpers.
"""
from pathlib import Path
from typing import Optional
import uuid

from config import ALLOWED_UPLOAD_EXTENSIONS, PORTAL_MAX_UPLOAD_BYTES
from services.storage_service import upload_provider_photo


async def _save_provider_upload(provider_id: int, upload, prefix: str) -> Optional[str]:
    """Saves portal-uploaded image and returns app-local or public URL."""
    if not upload or not getattr(upload, "filename", None):
        return None

    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        ext = ".jpg"

    data = await upload.read()
    if not data:
        return None
    if len(data) > PORTAL_MAX_UPLOAD_BYTES:
        return None

    uploaded_url = upload_provider_photo(
        provider_id=provider_id,
        data=data,
        extension=ext,
        prefix=prefix,
        content_type=getattr(upload, "content_type", None),
    )
    if uploaded_url:
        return uploaded_url

    target_dir = Path("static/uploads/providers") / str(provider_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex}{ext}"
    target_path = target_dir / filename
    with open(target_path, "wb") as handle:
        handle.write(data)

    return f"/static/uploads/providers/{provider_id}/{filename}"
