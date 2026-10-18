"""Callback credential expiry is independent of tenant/channel availability."""
from celery import shared_task


@shared_task
def wipe_messaging_credentials_task():
    from .messaging.senders import wipe_retired_credentials
    return wipe_retired_credentials()
