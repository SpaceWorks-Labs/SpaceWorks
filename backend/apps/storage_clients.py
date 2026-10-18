"""Apply shared transport budgets and writer fencing to domain-owned S3 clients."""
from contextlib import contextmanager
from contextvars import ContextVar

import boto3
from botocore.config import Config
from django.conf import settings


_qualifying = ContextVar("storage_qualification", default=False)


@contextmanager
def qualification():
    token = _qualifying.set(True)
    try:
        yield
    finally:
        _qualifying.reset(token)


def s3_client(service, **kwargs):
    if service != "s3":
        raise ValueError("This factory only accepts S3 clients.")
    from apps.storage_capabilities.budget import client_options
    options = client_options()
    if options:
        kwargs["config"] = (kwargs.get("config") or Config()).merge(Config(**options))
    # Independent audit/offsite credentials must not acquire the private token.
    if kwargs.get("aws_access_key_id") == settings.AWS_ACCESS_KEY_ID:
        token = getattr(settings, "AWS_SESSION_TOKEN", "")
        if token:
            kwargs.setdefault("aws_session_token", token)
    client = boto3.client(service, **kwargs)

    def before_call(params, context=None, **unused):
        from apps.operations.cloud_runtime import managed, check
        from apps.backup.cloud_continuity import check_operation
        check_operation()
        if managed():
            check()
        if params.get("Bucket") and not _qualifying.get() and not (context or {}).get("is_presign_request"):
            from apps.storage_capabilities.runtime import capabilities_for
            required = params["Bucket"] in {settings.AWS_STORAGE_BUCKET_NAME, settings.PUBLIC_IMAGE_BUCKET}
            capabilities_for(client, params["Bucket"], required=required)

    client.meta.events.register("before-parameter-build.s3", before_call)
    return client
