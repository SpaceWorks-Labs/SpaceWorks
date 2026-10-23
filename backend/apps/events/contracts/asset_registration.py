"""B runtime installation with lazy bounded storage clients and real readers."""

import sys

from django.conf import settings

from apps.events.certificate_storage import _client
from apps.events.submissions.api_runtime import SubmissionRuntime, install_runtime
from apps.events.submissions.read_policy import EventAssetReader
from apps.events.submissions.storage import EventAssetStorage
from .read_registration import AssetPolicy, admin_read_purpose, public_asset_resolver
from .saved_resume_registration import SavedResumeProvider


class StorageClient:
    """Startup remains query/network free; SDK construction happens on first use."""
    def __init__(self, *, public=False):
        self.public = public

    def __getattr__(self, name):
        endpoint = settings.AWS_S3_PUBLIC_ENDPOINT_URL if self.public else settings.AWS_S3_ENDPOINT_URL
        return getattr(_client(endpoint), name)


def read_range(locator, *, start, length, timeout_seconds):
    kwargs = {"Bucket": locator.bucket, "Key": locator.key, "Range": f"bytes={start}-{start+length-1}"}
    if locator.version_id:
        kwargs["VersionId"] = locator.version_id
    response = StorageClient().get_object(**kwargs)
    try:
        return response["Body"].read(length)
    finally:
        response["Body"].close()


def install():
    storage = EventAssetStorage(StorageClient(), StorageClient(public=True), settings.AWS_STORAGE_BUCKET_NAME)
    policy = AssetPolicy()
    install_runtime(SubmissionRuntime(storage=storage,
        asset_reader=EventAssetReader(policy=policy, bucket=storage.bucket),
        participant_reader=EventAssetReader(policy=policy, bucket=storage.bucket, participant=True),
        storage_reader=read_range,
        scan_options={"backend": getattr(settings, "EVENT_ASSET_SCAN_BACKEND", "none"),
                      "host": getattr(settings, "EVENT_ASSET_CLAMAV_HOST", None),
                      "port": getattr(settings, "EVENT_ASSET_CLAMAV_PORT", 3310)},
        sandbox_command=(sys.executable, "-m", "apps.events.submissions.probe_sandbox"),
        admin_read_purpose=admin_read_purpose, public_asset_resolver=public_asset_resolver,
        saved_resume_provider=SavedResumeProvider(storage)))
