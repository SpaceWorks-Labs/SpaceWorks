"""Platform email for the organization review workflow (applicant and superadmins).

Same shape as `hosting_requests/notifications.py`: platform mail (no tenant, never gated
by a tenant's `email` module), sent after commit, and a send failure is logged and
swallowed so mail can never roll back or break a review transition.
"""
import logging

from django.db import transaction
from django.utils.translation import gettext

from apps.accounts.models import User
from apps.integrations.dispatch import dispatch_email

logger = logging.getLogger(__name__)


def _send(org_id, *, to_email, subject, body, event, audience):
    try:
        dispatch_email(
            to_email=to_email, subject=subject, text_body=body, makerspace=None,
            connection="platform", stream="governance", event=event, audience=audience,
            persist_body=False, sync=True,
        )
    except Exception:
        # No exception text: provider failures can carry credentials or addresses.
        logger.warning(f"{event}_failed", extra={"organization_id": org_id})


def _superadmin_emails():
    rows = User.objects.filter(
        is_active=True, is_superuser=True, access_status=User.AccessStatus.ACTIVE,
    ).exclude(email="").values_list("email", flat=True)
    return [e.strip() for e in rows if e and e.strip()]


def notify_submitted(org):
    org_id, name = org.pk, org.name
    body = gettext('The organization "{name}" is waiting for review.').format(name=name)

    def _go():
        for email in _superadmin_emails():
            _send(org_id, to_email=email, subject=gettext("New organization to review"), body=body,
                  event="organization_review_submitted", audience="superadmin")
    transaction.on_commit(_go)


def notify_decision(org, action, reason):
    creator = org.created_by
    to_email = (creator.email if creator else "") or ""
    if not to_email:
        return
    org_id, name = org.pk, org.name
    subjects = {
        "approved": gettext("Your organization was approved"),
        "declined": gettext("Your organization was not approved"),
        "changes_requested": gettext("Changes requested for your organization"),
        "suspended": gettext("Your organization was suspended"),
        "reactivated": gettext("Your organization was reactivated"),
    }
    subject = subjects.get(action)
    if subject is None:
        return
    body = gettext('Update on the organization "{name}": {subject}.').format(name=name, subject=subject)
    if reason:
        body += "\n\n" + gettext("Reason: {reason}").format(reason=reason)
    transaction.on_commit(lambda: _send(
        org_id, to_email=to_email, subject=subject, body=body,
        event=f"organization_review_{action}", audience="applicant",
    ))
