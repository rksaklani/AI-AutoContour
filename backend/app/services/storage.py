"""S3 / MinIO object storage client.

Uses boto3 against a MinIO endpoint (S3-compatible). Provides upload, download,
presigned URL generation, and bucket bootstrapping.
"""

from __future__ import annotations

import io
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )


@lru_cache
def _public_client():
    """Client configured with the browser-facing endpoint for presigned URLs."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    client = _client()
    bucket = settings.S3_BUCKET
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        logger.info("Creating bucket %s", bucket)
        client.create_bucket(Bucket=bucket)


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    _client().put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def get_object(key: str) -> bytes:
    resp = _client().get_object(Bucket=settings.S3_BUCKET, Key=key)
    return resp["Body"].read()


def get_object_stream(key: str) -> io.BytesIO:
    return io.BytesIO(get_object(key))


def delete_prefix(prefix: str) -> None:
    client = _client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix):
        objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=settings.S3_BUCKET, Delete={"Objects": objects})


def presigned_get_url(key: str, expires: int = 3600) -> str:
    return _public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )
