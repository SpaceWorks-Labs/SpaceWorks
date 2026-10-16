"""Tenant-local identity copies. Use save() so scoped PII envelopes are rewritten."""

from django.conf import settings
from django.db.models import Q

from apps.accounts.account_deletion_discovery import _model
from apps.accounts.models_account_purge import AccountPurgeObject
from apps.inventory import public_image_storage


def _rows(label, **filters):
    model = _model(label)
    return model.objects.filter(**filters) if model is not None else ()


def _scrub(rows, values):
    for row in rows:
        fields = values(row) if callable(values) else values
        for field, value in fields.items():
            setattr(row, field, value)
        row.save(update_fields=list(fields))


def scrub_email_logs(user, makerspace_id, address):
    # to_email is scoped ciphertext at rest, so a SQL equality predicate misses it.
    for row in _rows("integrations.EmailLog", makerspace_id=makerspace_id).iterator():
        if row.recipient_id == user.pk or (address and row.to_email.strip().lower() == address.lower()):
            _scrub([row], {"to_email": "", "subject": "", "text_body": "", "html_body": ""})


def _profiles(user, makerspace_id):
    for profile in _rows("makerspaces.MemberProfile", membership__user=user,
                         membership__makerspace_id=makerspace_id):
        keys = [profile.avatar_key, *profile.projects.values_list("image_key", flat=True)]
        for key in set(keys) - {""}:
            # A missing object has no bytes to account for. A storage outage raises
            # and rolls back, leaving both the owning row and its key for a retry.
            size = public_image_storage.object_size(key)
            AccountPurgeObject.objects.get_or_create(
                user=user, makerspace_id=makerspace_id, bucket=settings.PUBLIC_IMAGE_BUCKET,
                object_key=key, defaults={"size_bytes": size or 0},
            )
        profile.delete()


def scrub_tenant(user, makerspace_id, *, username, address):
    _profiles(user, makerspace_id)
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
        owned = jobs.objects.filter(Q(member=user) | Q(member__isnull=True, requester=user),
                                    makerspace_id=makerspace_id)
        _scrub(owned, {"requester_name": "", "contact_email": "", "contact_phone": ""})
    _scrub(_rows("makerspaces.MembershipRequest", user=user, makerspace_id=makerspace_id), {
        "invite_email": "", "application_answers": None,
    })
    scrub_email_logs(user, makerspace_id, address)
    for label in ("integrations.PushDevice", "notifications.NotificationInboxRow"):
        rows = _rows(label, user=user, makerspace_id=makerspace_id)
        if hasattr(rows, "delete"):
            rows.delete()
