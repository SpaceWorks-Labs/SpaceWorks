"""Tenant-local identity copies. Use save() so scoped PII envelopes are rewritten.

Rows are read through ``backup.capture_managers.every_row`` (both membership tracks).
It scrubs the person AND each shell merged into them (``aliases``); a shell's profile
objects are journalled under the person (``journal_user``) so one drain and one progress
row cover them. B2's per-space restore re-runs it for erased accounts, shells included.
"""

from django.conf import settings
from django.db.models import Q

from apps.accounts.account_deletion_discovery import _model
from apps.accounts.models_account_purge import AccountPurgeObject
from apps.backup.capture_managers import every_row
from apps.inventory import public_image_storage


def _rows(label, **filters):
    model = _model(label)
    return every_row(model).filter(**filters) if model is not None else ()


def _scrub(rows, values):
    for row in rows:
        fields = values(row) if callable(values) else values
        for field, value in fields.items():
            setattr(row, field, value)
        row.save(update_fields=list(fields))


def scrub_email_logs(user, makerspace_id, address):
    from apps.accounts.models import User
    address_is_exclusive = bool(address and not User.objects.exclude(pk=user.pk).filter(
        email__iexact=address,
    ).exists())
    rows = _rows("integrations.EmailLog", makerspace_id=makerspace_id)
    values = {"to_email": "", "subject": "", "text_body": "", "html_body": "",
              "provider_message_id": ""}
    if makerspace_id is None:
        # Platform logs have no tenant DEK and are excluded from scoped encryption.
        # Read their keyless address projection only for ownership matching; the
        # strict mapped reader correctly refuses persisted non-envelope values.
        for pk, recipient_id, to_email in rows.values_list("pk", "recipient_id", "to_email").iterator():
            if recipient_id == user.pk or (recipient_id is None and address_is_exclusive and to_email.strip().lower() == address.lower()):
                _scrub(rows.filter(pk=pk), values)
        return
    # Tenant to_email is ciphertext at rest; match only authenticated model reads.
    for row in rows.iterator():
        if row.recipient_id == user.pk or (row.recipient_id is None and address_is_exclusive and row.to_email.strip().lower() == address.lower()):
            _scrub([row], values)


def _profiles(user, makerspace_id, journal_user):
    for profile in _rows("makerspaces.MemberProfile", membership__user=user,
                         membership__makerspace_id=makerspace_id):
        keys = [profile.avatar_key, *profile.projects.values_list("image_key", flat=True)]
        for key in set(keys) - {""}:
            # A missing object has no bytes to account for. A storage outage raises
            # and rolls back, leaving both the owning row and its key for a retry.
            size = public_image_storage.object_size(key)
            AccountPurgeObject.objects.get_or_create(
                user=journal_user, makerspace_id=makerspace_id, bucket=settings.PUBLIC_IMAGE_BUCKET,
                object_key=key, defaults={"size_bytes": size or 0},
            )
        profile.delete()


def scrub_tenant(user, makerspace_id, *, username, address, journal_user=None, aliases=True):
    """Scrub ``user``'s copies in one tenant, then (``aliases``) every shell merged into them."""
    from apps.integrations.messaging.purge import purge_user
    purge_user(user, makerspace_id)
    _profiles(user, makerspace_id, journal_user or user)
    _scrub(_rows("hardware_requests.HardwareRequest", requester=user, makerspace_id=makerspace_id), {
        "requester_username": username, "requester_name": "",
        "requester_contact_email": "", "requester_contact_phone": "",
    })
    _scrub(_rows("bookings.Booking", member=user, space__makerspace_id=makerspace_id), lambda row: {
        "name": "Deleted member", "email": f"deleted+{row.pk}@invalid.invalid",
        "phone": "Deleted", "note": "", "custom_answers": None,
    })
    _scrub(_rows("events.EventRegistration", member=user, event__makerspace_id=makerspace_id), lambda row: {
        "name": "Deleted member", "email": f"deleted+{row.pk}@invalid.invalid",
        "phone": "", "custom_answers": None,
    })
    jobs = _model("machines.MachineServiceRequest")
    if jobs is not None:
        owned = every_row(jobs).filter(Q(member=user) | Q(member__isnull=True, requester=user),
                                    makerspace_id=makerspace_id)
        _scrub(owned, {"requester_name": "", "contact_email": "", "contact_phone": ""})
    _scrub(_rows("makerspaces.MembershipRequest", user=user, makerspace_id=makerspace_id), {
        "invite_email": "", "application_answers": None,
    })
    scrub_email_logs(user, makerspace_id, address)
    attempts = _model("integrations.PushDeliveryAttempt")
    if attempts is not None:
        # The recipient snapshot still owns history after device reassignment.
        every_row(attempts).filter(Q(recipient=user) | Q(push_device__user=user),
                                delivery_log__makerspace_id=makerspace_id).delete()
    # CASCADE removes member deliveries through either the inbox row or device,
    # including rows whose other endpoint now belongs to a different account.
    for label in ("integrations.PushDevice", "notifications.NotificationInboxRow", "notifications.BrowserFirebaseRegistration"):
        rows = _rows(label, user=user, makerspace_id=makerspace_id)
        if hasattr(rows, "delete"):
            rows.delete()
    if aliases:
        from apps.accounts.account_deletion_discovery import aliases as merged
        for shell in merged(user)[1:]:
            # A shell's own address was scrubbed at merge; recipient-linked rows still match.
            scrub_tenant(shell, makerspace_id, username=username, address="",
                         journal_user=journal_user or user, aliases=False)
