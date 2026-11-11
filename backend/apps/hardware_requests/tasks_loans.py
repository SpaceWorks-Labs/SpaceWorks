"""Loan reservation sweep (lane L12): pickup expiry, waitlist offer lapses and pickup-expiring reminders."""

from celery import shared_task


@shared_task(name="apps.hardware_requests.tasks_loans.sweep_loan_pickups_task")
def sweep_loan_pickups_task():
    from apps.hardware_requests.pickup_reminders import remind_expiring_pickups
    from apps.hardware_requests.request_lifecycle import expire_due_requests
    expired = expire_due_requests()
    # Decision 221(f): remind borrowers whose accepted request is about to lapse (after the expiry pass,
    # so a request that just expired is never reminded).
    remind_expiring_pickups()
    return expired
