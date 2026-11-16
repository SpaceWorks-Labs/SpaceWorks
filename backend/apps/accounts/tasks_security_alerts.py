"""Celery delivery of one security alert; the only argument is the alert's id."""

from celery import shared_task


@shared_task(name="apps.accounts.tasks_security_alerts.deliver_security_alert_task", ignore_result=True)
def deliver_security_alert_task(alert_id):
    from apps.accounts.security_alerts import deliver
    return deliver(alert_id)
