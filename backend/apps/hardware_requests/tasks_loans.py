"""Loan reservation sweep (lane L12): pickup expiry and waitlist offer lapses."""

from celery import shared_task


@shared_task(name="apps.hardware_requests.tasks_loans.sweep_loan_pickups_task")
def sweep_loan_pickups_task():
    from apps.hardware_requests.request_lifecycle import expire_due_requests
    return expire_due_requests()
