#!/usr/bin/env python3
"""Read-only deployment size measurement. Output counts only, never locators/keys."""
import json
import logging
import os
import sys
import time
import uuid


def main():
    logging.disable(logging.CRITICAL)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from apps.evidence.storage import _client
    from botocore.config import Config
    import boto3
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        size = cursor.fetchone()[0]
    config = _client().meta.config.merge(Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1}))
    client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                          aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                          aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                          region_name=settings.AWS_S3_REGION_NAME, config=config)
    objects, count = 0, 0
    deadline = time.monotonic() + 60
    for bucket in {settings.AWS_STORAGE_BUCKET_NAME, settings.PUBLIC_IMAGE_BUCKET}:
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for item in page.get("Contents", ()):
                objects += item["Size"]
                count += 1
            if count > 1_000_000 or time.monotonic() > deadline:
                raise ValueError("Capacity inventory exceeds supervised bound.")
    archive_bytes = 0
    if len(sys.argv) > 1 and sys.argv[1]:
        from apps.backup.models import RestoreOperation
        restore = RestoreOperation.objects.select_related("archive").get(pk=uuid.UUID(sys.argv[1]))
        public = boto3.client("s3", endpoint_url=settings.AWS_S3_PUBLIC_ENDPOINT_URL,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                              region_name=settings.AWS_S3_REGION_NAME, config=config)
        archive_bytes = public.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                                          Key=restore.archive.object_key)["ContentLength"]
    print(json.dumps({"database_bytes": size, "object_bytes": objects, "archive_bytes": archive_bytes}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Cannot measure deployment database/object capacity; no operation admitted.")
