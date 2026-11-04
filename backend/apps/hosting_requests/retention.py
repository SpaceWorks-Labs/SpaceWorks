"""Daily retention for hosting requests.

1. Public submissions nobody confirmed within 48 hours are deleted outright.
2. Dead requests keep their decision record but lose the applicant's personal details
   90 days after they died: rejected (from ``decided_at``), withdrawn (from
   ``withdrawn_at``), invitations never completed (from ``invite_expires_at``) and
   requests for changes never answered (from ``changes_requested_at``). Review-history
   notes are wiped with them; the history rows themselves stay as the decision record.

The applicant mail logs (``EmailLog`` rows with ``source_kind="hosting_request"``) go
with them, since they hold the applicant's address. Bounded per run, row-locked with
SKIP LOCKED so a concurrent transition is never blocked, and logged as counts only:
deletions and redactions are deliberately not audited.

Runs regardless of managed mode: a deployment that left managed hosting must still
honour the wipe for rows it already holds.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.hosting_requests.models import HostingRequest
from apps.hosting_requests.notifications import SOURCE_KIND
from apps.integrations.models import EmailLog

logger = logging.getLogger(__name__)

BATCH = 500
MAX_LOOPS = 10
RETENTION = timedelta(days=90)
S = HostingRequest.Status
REDACTED_VALUES = {
    "applicant_name": "", "applicant_email": "", "applicant_phone": "", "description": "",
    "space_website_url": "", "invite_note": "", "new_organization_name": "",
    "invite_token_digest": None, "access_token_digest": None, "changes_note": "",
}


def _expired_unverified(now):
    return HostingRequest.objects.filter(
        source=HostingRequest.Source.PUBLIC, status=S.PENDING_VERIFICATION,
        verification_expires_at__lt=now,
    )


def _dead_unredacted(now):
    cutoff = now - RETENTION
    return HostingRequest.objects.filter(redacted_at__isnull=True).filter(
        Q(status=S.REJECTED, decided_at__lt=cutoff)
        | Q(status=S.WITHDRAWN, withdrawn_at__lt=cutoff)
        # X31: a request for changes nobody answered in 90 days is as dead as a withdrawal.
        | Q(status=S.CHANGES_REQUESTED, changes_requested_at__lt=cutoff)
        | Q(
            source=HostingRequest.Source.INVITED,
            status__in=(S.INVITED, S.PENDING_VERIFICATION),
            invite_expires_at__lt=cutoff,
        )
    )


def _locked_ids(queryset):
    return list(
        queryset.select_for_update(skip_locked=True).order_by("pk").values_list("pk", flat=True)[:BATCH]
    )


def _delete_mail_logs(ids):
    EmailLog.objects.filter(source_kind=SOURCE_KIND, source_id__in=ids).delete()


def _delete_batch(now):
    with transaction.atomic():
        ids = _locked_ids(_expired_unverified(now))
        if ids:
            _delete_mail_logs(ids)
            HostingRequest.objects.filter(pk__in=ids).delete()
        return len(ids)


def _redact_batch(now):
    with transaction.atomic():
        ids = _locked_ids(_dead_unredacted(now))
        if ids:
            _delete_mail_logs(ids)
            HostingRequest.objects.filter(pk__in=ids).update(
                **REDACTED_VALUES, redacted_at=now, updated_at=now,
            )
            from apps.hosting_requests.models import HostingRequestRevision
            HostingRequestRevision.objects.filter(request_id__in=ids).update(note="")
        return len(ids)


def _loop(step, now):
    total = 0
    for _ in range(MAX_LOOPS):
        count = step(now)
        total += count
        if count < BATCH:
            break
    return total


def sweep(now=None):
    now = now or timezone.now()
    result = {"deleted": _loop(_delete_batch, now), "redacted": _loop(_redact_batch, now)}
    logger.info("hosting_request_retention_swept", extra=result)
    return result
