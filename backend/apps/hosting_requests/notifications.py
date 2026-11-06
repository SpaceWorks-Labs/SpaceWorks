"""Platform email for hosting requests.

Every message is platform mail (no tenant, never gated by a tenant's ``email`` module),
sent synchronously with ``persist_body=False`` because most of them embed a live bearer
link. Mail to the applicant carries ``source_kind="hosting_request"`` so the retention
sweep can delete those ``EmailLog`` rows together with the request's personal details.
A send failure is logged and swallowed: mail never rolls back or breaks a transition.
"""

from django.utils.translation import gettext
import logging
from urllib.parse import urlencode

from django.db import transaction
from django.urls import reverse

from apps.accounts.models import User
from apps.hosting_requests.availability import public_base_url
from apps.integrations.delivery_sources import DeliverySource, register
from apps.integrations.dispatch import dispatch_email

logger = logging.getLogger(__name__)

SOURCE_KIND = "hosting_request"


def _first_delivery_only(log):
    # The body is never stored, so a retry of a stored row would send an empty
    # message. Only the in-memory first delivery carries content.
    return bool(log.text_body or log.html_body)


def register_delivery_source():
    register(SOURCE_KIND, DeliverySource(_first_delivery_only, digestible=False))


def status_link(raw_token):
    return f"{public_base_url()}/hosting/request#{urlencode({'token': raw_token})}"


def invite_link(raw_token):
    return f"{public_base_url()}/hosting/invite#{urlencode({'token': raw_token})}"


def _send(row_id, *, to_email, subject, text_body, event, audience, applicant=True):
    try:
        log = dispatch_email(
            to_email=to_email, subject=subject, text_body=text_body, makerspace=None,
            connection="platform", stream="governance", event=event, audience=audience,
            persist_body=False, sync=True,
            source_kind=SOURCE_KIND if applicant else "",
            source_id=row_id if applicant else None,
        )
        return getattr(log, "status", "unavailable")
    except Exception:
        # No exception text: provider failures can carry credentials or addresses.
        logger.warning(f"{event}_failed", extra={"hosting_request_id": row_id})
        return "unavailable"


def schedule_verify(row, raw_token):
    row_id, to_email, link = row.pk, row.applicant_email, status_link(raw_token)
    # Generic on purpose: nothing the applicant typed is echoed to an unconfirmed address.
    body = (
        "Someone asked to host a makerspace on Space Works using this email address.\n\n"
        f"Confirm the request: {link}\n\n"
        "This link expires in 48 hours. After you confirm, the same link shows your "
        "request's status.\n\n"
        "If you didn't ask to host a makerspace on Space Works, ignore this email and "
        "nothing will happen."
    )
    transaction.on_commit(lambda: _send(
        row_id, to_email=to_email, subject=gettext("Confirm your Space Works hosting request"),
        text_body=body, event="hosting_request_verify", audience="applicant",
    ))


def schedule_new(row):
    row_id = row.pk
    transaction.on_commit(lambda: _send_new(row_id))


def _send_new(row_id):
    try:
        path = reverse("admin:hosting_requests_hostingrequest_changelist")
        recipients = User.objects.filter(
            is_active=True, is_superuser=True, access_status=User.AccessStatus.ACTIVE,
        ).exclude(email="").values_list("email", flat=True)
    except Exception:
        logger.warning("hosting_request_new_failed", extra={"hosting_request_id": row_id})
        return
    body = f"A new hosting request is waiting for review.\n\nReview it in the control plane: {path}"
    for email in recipients:
        email = (email or "").strip()
        if email:
            _send(row_id, to_email=email, subject=gettext("New hosting request"), text_body=body,
                  event="hosting_request_new", audience="superadmin", applicant=False)


def schedule_accepted(row):
    row_id, to_email, space = row.pk, row.applicant_email, row.space_name
    body = (
        f"Your request to host {space} on Space Works has been accepted.\n\n"
        "The platform team will set up your space and contact you."
    )
    transaction.on_commit(lambda: _send(
        row_id, to_email=to_email, subject=gettext("Your hosting request was accepted"),
        text_body=body, event="hosting_request_accepted", audience="applicant",
    ))


def schedule_rejected(row):
    row_id, to_email, space, reason = (
        row.pk, row.applicant_email, row.space_name, row.rejection_reason,
    )
    body = (
        f"Your request to host {space} on Space Works was not accepted.\n\n"
        f"Reason: {reason}"
    )
    transaction.on_commit(lambda: _send(
        row_id, to_email=to_email, subject=gettext("Your hosting request was not accepted"),
        text_body=body, event="hosting_request_rejected", audience="applicant",
    ))


def schedule_changes_requested(row, raw_token):
    row_id, to_email, space, note = row.pk, row.applicant_email, row.space_name, row.changes_note
    body = (f"The platform team asked for some changes to your request to host {space} on Space Works.\n\n"
            f"What to change: {note}\n\nUpdate and resubmit your request: {status_link(raw_token)}\n")
    transaction.on_commit(lambda: _send(
        row_id, to_email=to_email, subject=gettext("Changes requested on your hosting request"),
        text_body=body, event="hosting_request_changes_requested", audience="applicant",
    ))


def send_invitation(row, raw_token, inviter_name):
    """Send now (after the creating transaction committed) and report delivery status."""
    link = invite_link(raw_token)
    lines = [
        f"{inviter_name} invited you to host your makerspace on Space Works.",
        "",
        f"Open the invitation: {link}",
        f"It expires on {row.invite_expires_at:%Y-%m-%d}.",
    ]
    if row.invite_note:
        lines += ["", f"Their note: {row.invite_note}"]
    lines += ["", "If you weren't expecting this, you can ignore it."]
    status = _send(
        row.pk, to_email=row.applicant_email,
        subject=gettext('{inviter_name} invited you to host your makerspace on Space Works').format(inviter_name=inviter_name),
        text_body="\n".join(lines), event="hosting_invitation", audience="applicant",
    )
    return link, status
