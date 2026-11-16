"""Callback credential expiry is independent of tenant/channel availability."""
from celery import shared_task
from .notification_cutover import guarded, state


@shared_task
@guarded()
def wipe_messaging_credentials_task():
    if state().route != "canonical":
        return 0
    from .messaging.senders import wipe_retired_credentials
    return wipe_retired_credentials()
