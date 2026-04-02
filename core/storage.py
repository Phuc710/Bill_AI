"""
Supabase Storage service.
Uploads PIL images to Bills bucket and returns public URL.
Falls back gracefully (returns None) if Supabase is unreachable.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Optional

from PIL import Image

from core.config import Config

log = logging.getLogger("billai.storage")


class StorageService:
    _client = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            from supabase import create_client  # type: ignore
            cls._client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
        return cls._client

    @classmethod
    def upload_image(
        cls,
        image: Image.Image,
        bill_id: str,
        kind: str,  # "Original" | "Cropped"
    ) -> Optional[str]:
        """Upload a PIL image and return its public URL, or None on failure."""
        if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_KEY:
            log.debug("Supabase not configured, skipping upload.")
            return None

        today = datetime.now(timezone.utc)
        suffix = "_crop" if kind == "Cropped" else ""
        path = f"{kind}/{today.year}/{today.month:02d}/{today.day:02d}/{bill_id}{suffix}.jpg"

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=85)
        buf.seek(0)

        try:
            cls._get_client().storage.from_(Config.SUPABASE_BUCKET).upload(
                path=path,
                file=buf.read(),
                file_options={"content-type": "image/jpeg", "upsert": "true"},
            )
            url = (
                f"{Config.SUPABASE_URL}/storage/v1/object/public"
                f"/{Config.SUPABASE_BUCKET}/{path}"
            )
            log.debug(f"Storage upload OK [{kind}]: {url}")
            return url
        except Exception as exc:
            log.warning(f"Storage upload FAILED [{kind}] bill={bill_id}: {exc}")
            return None

    @classmethod
    def delete_images(cls, bill_id: str) -> None:
        """Delete all images for a bill (original + cropped)."""
        if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_KEY:
            return
        today = datetime.now(timezone.utc)
        paths = [
            f"Original/{today.year}/{today.month:02d}/{today.day:02d}/{bill_id}.jpg",
            f"Cropped/{today.year}/{today.month:02d}/{today.day:02d}/{bill_id}_crop.jpg",
        ]
        try:
            cls._get_client().storage.from_(Config.SUPABASE_BUCKET).remove(paths)
        except Exception as exc:
            log.warning(f"Storage delete FAILED bill={bill_id}: {exc}")
