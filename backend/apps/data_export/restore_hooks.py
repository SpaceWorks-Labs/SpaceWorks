"""Restore seams must clear copied download bearers; the download route is anonymous."""

from apps.data_export.models import DataExportJob

CLEARED_DOWNLOAD_BEARER = {
    "download_token_digest": "",
    "download_token_expires_at": None,
    "download_token_consumed_at": None,
    "download_issued_to": None,
}


def invalidate_download_tokens_after_restore(*, using="default"):
    """Restore hook: copied bearer digests must never remain usable."""
    return DataExportJob.objects.using(using).exclude(download_token_digest="").update(
        **CLEARED_DOWNLOAD_BEARER
    )


def strip_download_bearer(fixture):
    return {**fixture, "fields": {**fixture["fields"], **CLEARED_DOWNLOAD_BEARER}}
