"""Core ledger maintenance, independently of the removable rail."""

from celery import shared_task


@shared_task(name="apps.payments.tasks.issue_missing_bills_task")
def issue_missing_bills_task():
    from .bill_sweeper import issue_missing_bills
    return issue_missing_bills()


@shared_task(name="apps.payments.tasks.rebuild_refund_cases_task")
def rebuild_refund_cases_task():
    from .refund_case_sweeper import rebuild_missed_refund_cases
    return rebuild_missed_refund_cases()


@shared_task(name="apps.payments.tasks.run_gateway_poll_task")
def run_gateway_poll_task():
    from .gateway_poll import run_gateway_poll
    return run_gateway_poll()


# Release 2 lane L18: pledge periods and sponsor perk reminders (registered under their own names).
from apps.payments.donations.tasks import raise_pledges_task, remind_perks_task  # noqa: E402,F401
