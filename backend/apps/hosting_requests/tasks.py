from celery import shared_task

from apps.hosting_requests.retention import sweep


@shared_task(name="apps.hosting_requests.tasks.sweep_hosting_requests_task")
def sweep_hosting_requests_task():
    return sweep()
