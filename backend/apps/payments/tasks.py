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
