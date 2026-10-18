"""A retry cannot erase uncertain provider acceptance or a deferred allowance."""
from django.utils import timezone


def unresolved_acceptance(log):
    from .mail_providers.budget_config import free_profile
    if not free_profile():
        return False
    from apps.operations.models import CloudEmailReservation
    return CloudEmailReservation.objects.filter(log_id=log.pk, state__in=["reserved", "uncertain"]).exists()


def rearm_rejected_configuration(log):
    """Operator retry needs definite nonacceptance and a newer accepted test.

    Existing receipts are never released/relabelled here. Source retry authority is
    still checked by retry_email_log in the same transaction.
    """
    from .mail_providers.budget_config import free_profile
    if not free_profile() or log.email_retryable or unresolved_acceptance(log):
        return False
    if log.email_retry_at and log.email_retry_at > timezone.now():
        return False
    from apps.operations.models import CloudEmailReservation
    receipts = CloudEmailReservation.objects.filter(log_id=log.pk)
    if not receipts.exists() or receipts.exclude(state="released").exists():
        return False
    from apps.audit.models import AuditLog
    if not AuditLog.objects.filter(action="email.transport_tested", makerspace_id=log.makerspace_id,
                                  meta__accepted=True, created_at__gt=log.updated_at).exists():
        return False
    log.email_retryable, log.email_retry_at = True, None
    log.save(update_fields=["email_retryable", "email_retry_at"])
    return True
