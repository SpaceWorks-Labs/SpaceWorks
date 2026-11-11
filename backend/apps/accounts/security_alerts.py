"""Security alert emails with a single-use "this wasn't me" link (#62; lane S-B).

Kinds (``login_security_contract.ALERT_KINDS``): a sign-in from a new device, a password
change, a second-factor change, an account lockout (at most one an hour). Each is a
``SecurityAlert`` row plus platform mail (``makerspace=None``, stream ``account``, never
persisted, exempt from every opt-out). The emailed code of the unusual-login check is the
same kind of mail without a row or link.

The row is created with an unusable placeholder digest; only delivery mints the nonce,
writes its digest and puts the link in the mail, so the nonce never crosses the task
queue (the Celery argument is the alert id only). Labels (network, device) are cleared
once the mail is sent; an unsent alert keeps them until it expires
(``SECURITY_ALERT_LINK_TTL_DAYS``), and retention deletes the row 30 days after that.
"""

from django.utils.translation import gettext
import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.login_security_contract import (
    ALERT_LOCKOUT, ALERT_MFA_CHANGED, ALERT_NEW_DEVICE, ALERT_PASSWORD_CHANGED,
)

logger = logging.getLogger(__name__)
TOKEN_SALT = "accounts.security_alert"
PLACEHOLDER = "p"  # a sha256 hex digest never starts with "p": the alert is not sent yet
LOCKOUT_EVERY = timedelta(hours=1)
SUBJECTS = {
    ALERT_NEW_DEVICE: "New sign-in to your Space Works account",
    ALERT_PASSWORD_CHANGED: "Your Space Works password was changed",
    ALERT_MFA_CHANGED: "Your two-step sign-in changed",
    ALERT_LOCKOUT: "Your Space Works account was locked",
}
EVENTS = {
    ALERT_NEW_DEVICE: "security_login_new_device", ALERT_PASSWORD_CHANGED: "security_password_changed",
    ALERT_MFA_CHANGED: "security_mfa_changed", ALERT_LOCKOUT: "security_account_locked",
}
LOGIN_CODE_EVENT = "security_login_code"


def nonce_digest(nonce):
    return hashlib.sha256(nonce.encode()).hexdigest()


def create(user, kind, *, network_label=None, ua_label=None):
    """Queue one alert for ``user`` after commit; None when they have no email."""
    from apps.accounts.models import SecurityAlert
    if getattr(user, "pk", None) is None or not (user.email or "").strip():
        return None
    now = timezone.now()
    row = SecurityAlert.objects.create(
        user_id=user.pk, kind=kind, nonce_digest=PLACEHOLDER + secrets.token_hex(31),
        network_label=(network_label or None) and network_label[:120], ua_label=(ua_label or None) and ua_label[:120],
        sent_at=now, expires_at=now + timedelta(days=settings.SECURITY_ALERT_LINK_TTL_DAYS))
    pk = row.pk
    transaction.on_commit(lambda: enqueue(pk))
    return row


def new_device(user, *, network_label=None, ua_label=None):
    return create(user, ALERT_NEW_DEVICE, network_label=network_label, ua_label=ua_label)


def password_changed(user):
    return create(user, ALERT_PASSWORD_CHANGED)


def account_locked(user):
    from apps.accounts.models import SecurityAlert
    if SecurityAlert.objects.filter(user_id=user.pk, kind=ALERT_LOCKOUT,
                                    sent_at__gte=timezone.now() - LOCKOUT_EVERY).exists():
        return None
    return create(user, ALERT_LOCKOUT)


def on_mfa_changed(sender, user=None, change=None, **kwargs):
    if user is not None:
        create(user, ALERT_MFA_CHANGED)


def enqueue(alert_id):
    """Hand delivery to Celery when a worker exists; deliver inline otherwise."""
    from apps.integrations.mail_providers.outbox import enqueue_inline_allowed
    if enqueue_inline_allowed():
        try:
            from apps.accounts.tasks_security_alerts import deliver_security_alert_task
            deliver_security_alert_task.delay(alert_id)
            return
        except Exception:
            logger.warning("security_alert_enqueue_failed", exc_info=True)
    deliver(alert_id)


def link_for(row, nonce):
    token = signing.dumps({"a": row.pk, "n": nonce}, salt=TOKEN_SALT)
    base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
    return f"{base}/security/not-me#token={token}"


def deliver(alert_id):
    """Mint the link, send the mail, clear the labels. Safe to call twice."""
    from apps.accounts import audit_events
    from apps.accounts.models import SecurityAlert
    from apps.integrations.dispatch import dispatch_email
    with transaction.atomic():
        row = SecurityAlert.objects.select_for_update().select_related("user").filter(pk=alert_id).first()
        if row is None or not row.nonce_digest.startswith(PLACEHOLDER) or row.expires_at <= timezone.now():
            return False
        nonce = secrets.token_urlsafe(32)
        row.nonce_digest = nonce_digest(nonce)
        row.save(update_fields=["nonce_digest"])
    context = {"user": row.user, "alert": row, "link": link_for(row, nonce),
               "expires_days": settings.SECURITY_ALERT_LINK_TTL_DAYS}
    try:
        log = dispatch_email(
            to_email=row.user.email, subject=SUBJECTS[row.kind],
            text_body=render_to_string(f"email/security_{row.kind}.txt", context),
            html_body=render_to_string(f"email/security_{row.kind}.html", context),
            makerspace=None, stream="account", event=EVENTS[row.kind], audience="user",
            connection="platform", persist_body=False, sync=True, recipient_id=row.user_id)
        from apps.integrations.transient_mail import accepted
        sent = accepted(log)
    except Exception:
        logger.exception("security_alert_send_failed", extra={"kind": row.kind})
        sent = False
    if sent:
        SecurityAlert.objects.filter(pk=row.pk).update(network_label=None, ua_label=None)
        audit_events.record_auth_event(row.user, "auth.security_alert_sent", target=row.user,
                                       meta={"kind": row.kind})
    return sent


def send_login_code(user_id, code):
    from apps.accounts.models import User
    from apps.integrations.dispatch import dispatch_email
    user = User.objects.filter(pk=user_id).first()
    if user is None or not (user.email or "").strip():
        return False
    minutes = max(1, settings.LOGIN_CODE_TTL_SECONDS // 60)
    base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
    context = {"user": user, "code": code, "minutes": minutes, "reset_link": f"{base}/reset-password"}
    log = dispatch_email(
        to_email=user.email, subject=gettext("Your Space Works sign-in code"),
        text_body=render_to_string("email/security_login_code.txt", context),
        html_body=render_to_string("email/security_login_code.html", context),
        makerspace=None, stream="account", event=LOGIN_CODE_EVENT, audience="user",
        connection="platform", persist_body=False, sync=True, recipient_id=user.pk)
    from apps.integrations.transient_mail import accepted
    return accepted(log)
