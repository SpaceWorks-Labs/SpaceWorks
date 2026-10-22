"""Apply shared transport budgets and writer fencing to domain-owned S3 clients."""
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from threading import get_ident

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
    factory_context, creator = copy_context(), get_ident()

    def before_call(params, context=None, model=None, **unused):
        from apps.operations.cloud_runtime import managed, check
        from apps.backup.cloud_continuity import check_operation
        check_operation()
        if managed():
            check()
            if model.name not in {"GetObject", "HeadObject", "HeadBucket", "ListObjectsV2", "ListObjects",
                                  "ListObjectVersions", "ListMultipartUploads", "ListParts",
                                  "GetBucketVersioning", "GetBucketCors", "GetObjectLockConfiguration",
                                  "GetObjectRetention", "GetBucketLocation"}:
                from apps.operations.cloud_runtime import _writer
                from apps.backup.managed.capture import _capture
                if _writer.get() is None and _capture.get() is None:
                    from apps.backup.managed.writers import WriterFenceError
                    raise WriterFenceError("Managed storage writes require the original writer boundary.")
        if params.get("Bucket") and not _qualifying.get() and not (context or {}).get("is_presign_request"):
            from apps.storage_capabilities.runtime import capabilities_for
            required = params["Bucket"] in {settings.AWS_STORAGE_BUCKET_NAME, settings.PUBLIC_IMAGE_BUCKET}
            capabilities_for(client, params["Bucket"], required=required)
        if (getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
                and not _qualifying.get()):
            from apps.operations.cloud_quotas.transport import before
            before(client, params, model=model, context=context)

    def retained(callback):
        def run(*args, **event):
            bound = factory_context.copy()
            if get_ident() == creator and getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
                # Explicit promotion/staging admission occurs after client
                # construction. Carry only its reservation identity; the writer,
                # operation and deadline remain pinned to factory creation.
                from apps.operations.cloud_quotas.storage import _pending
                bound.run(_pending.set, _pending.get())
            def guarded():
                from apps.backup.cloud_continuity import check_operation
                from apps.operations.cloud_runtime import managed, check
                check_operation()
                if managed():
                    check()
                result = callback(*args, **event)
                check_operation()
                if managed():
                    check()
                return result
            try:
                return bound.run(guarded)
            finally:
                if get_ident() != creator:
                    # Django connections are thread-local. The original managed
                    # pin is a separate retained DB-API connection and is not
                    # closed here; SDK pool threads must not retain ORM sockets.
                    from django.db import connections
                    connections.close_all()
        return run

    client.meta.events.register("before-parameter-build.s3", retained(before_call))
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
        from functools import partial
        from apps.operations.cloud_quotas.transport import after, failed
        client.meta.events.register("after-call.s3", retained(partial(after, client)))
        client.meta.events.register("after-call-error.s3", retained(failed))
    return client
