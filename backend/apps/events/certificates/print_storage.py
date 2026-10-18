import hashlib

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from rest_framework.exceptions import APIException

from apps.events.certificate_storage import _client
from apps.object_storage import delete_all_versions


class PrintStorageUnavailable(APIException):
    status_code = 503
    default_detail = "Badge printing storage is temporarily unavailable."
    default_code = "print_storage_unavailable"


def put(key, content, mime):
    if not content or len(content) > 40 * 1024 * 1024:
        raise PrintStorageUnavailable("The print artifact exceeds the bounded size.")
    client = _client(settings.AWS_S3_ENDPOINT_URL)
    digest = hashlib.sha256(content).hexdigest()
    try:
        try:
            client.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=content,
                              ContentType=mime, IfNoneMatch="*")
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 412:
                raise
        read(key, digest)
        return len(content), digest
    except (BotoCoreError, ClientError, OSError) as exc:
        raise PrintStorageUnavailable() from exc


def read(key, digest):
    try:
        response = _client(settings.AWS_S3_ENDPOINT_URL).get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        body = response["Body"]
        try:
            content = body.read(40 * 1024 * 1024 + 1)
        finally:
            body.close()
        if len(content) > 40 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != digest:
            raise PrintStorageUnavailable()
        return content
    except (BotoCoreError, ClientError, OSError) as exc:
        raise PrintStorageUnavailable() from exc


def delete(key):
    try:
        delete_all_versions(_client(settings.AWS_S3_ENDPOINT_URL), bucket=settings.AWS_STORAGE_BUCKET_NAME, key=key)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise PrintStorageUnavailable() from exc
