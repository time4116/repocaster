from __future__ import annotations

from pathlib import Path

import boto3

from .config import Settings


def publish_to_s3(output_path: Path, metadata_path: Path, settings: Settings) -> str | None:
    if not settings.output_bucket:
        return None
    s3 = boto3.client("s3")
    key_prefix = f"actions/{output_path.stem}"
    audio_key = f"{key_prefix}/{output_path.name}"
    metadata_key = f"{key_prefix}/{metadata_path.name}"
    s3.upload_file(str(output_path), settings.output_bucket, audio_key)
    s3.upload_file(str(metadata_path), settings.output_bucket, metadata_key)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.output_bucket, "Key": audio_key},
        ExpiresIn=settings.presigned_url_ttl_seconds,
    )
