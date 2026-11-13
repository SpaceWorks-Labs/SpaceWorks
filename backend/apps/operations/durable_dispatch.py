"""Persisted work stays pending for explicit brokerless workers and free ticks."""
from django.conf import settings


def resident_delivery():
    return (getattr(settings, "CLOUD_TASK_PROFILE", "") != "brokerless"
            and getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") != "free")


def dispatch(task, *args, **kwargs):
    if resident_delivery():
        return task.delay(*args, **kwargs)
    return None
