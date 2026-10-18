"""Global ownership discovery for account departure, independent of member visibility.

The subject is always the authenticated account. Applying staff RBAC here would
miss account-only participation and historical rows in revoked/archived spaces.
"""

from django.apps import apps
from django.db.models import Q

from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.subject_runtime import RUNTIME_FIELDS
from apps.data_export.subject_selectors import SUBJECT_PATHS


def _model(label):
    try:
        return apps.get_model(label)
    except LookupError:
        # Deployment-tombstoned domains have no table to discover.
        return None


def tenant_ids(user):
    result = set()
    for label, paths in SUBJECT_PATHS.items():
        if label in RUNTIME_FIELDS:
            # Runtime rows have no portable DATASET_SPECS predicate. Discover
            # their tenant below, including both push ownership paths.
            continue
        model = _model(label)
        if model is None:
            continue
        own = Q()
        for path in paths:
            own |= Q(**{f"{path}_id": user.pk})
        predicate = DATASET_SPECS[label][1]
        rows = model.objects.filter(own)
        for path in (*predicate.any_paths, *predicate.local_or_global_paths):
            result.update(rows.values_list(path, flat=True))
    # These global/personal tables are intentionally not subject-export datasets.
    for label, owner, tenant in (
        ("events.EventStaffGrant", "user", "makerspace"),
        ("bookings.BookingSpaceStaffGrant", "user", "makerspace"),
        ("integrations.MessagingConsent", "user", "makerspace"),
        ("integrations.MessagingDelivery", "user", "makerspace"),
        ("payments.Payment", "member", "via_makerspace"),
        ("events.EventRegistration", "member", "registered_via_makerspace"),
        ("events.EventRegistration", "member", "payment_via_makerspace"),
        ("notifications.NotificationInboxRow", "user", "makerspace"),
        ("notifications.MemberNotificationPreference", "user", "makerspace"),
        ("integrations.PushDevice", "user", "makerspace"),
        ("integrations.NotificationEnvelope", "recipient", "makerspace"),
        ("integrations.NotificationDelivery", "envelope__recipient", "makerspace"),
        ("integrations.NotificationEndpoint", "user", "makerspace"),
        ("integrations.NotificationEndpointChallenge", "user", "makerspace"),
        ("integrations.EmailLog", "recipient", "makerspace"),
        ("accounts.DeviceActivityDay", "grant__user", "makerspace"),
        ("notifications.MemberPushDelivery", "inbox_row__user", "inbox_row__makerspace"),
        ("notifications.MemberPushDelivery", "envelope_delivery__envelope__recipient", "envelope_delivery__makerspace"),
        ("integrations.NotificationIngress", "signed_user", "makerspace_reference"),
        # The canonical parent carries the tenant; the inbox row is optional (SET_NULL).
        ("notifications.MemberPushDelivery", "push_device__user", "envelope_delivery__makerspace"),
        ("integrations.PushDeliveryAttempt", "recipient", "delivery_log__makerspace"),
        ("integrations.PushDeliveryAttempt", "push_device__user", "delivery_log__makerspace"),
    ):
        model = _model(label)
        if model is not None:
            result.update(model.objects.filter(**{owner: user}).values_list(tenant, flat=True))
    model = _model("machines.MachineServiceRequest")
    if model is not None:
        result.update(model.objects.filter(member__isnull=True, requester=user)
                      .values_list("makerspace_id", flat=True))
    # Address-only delivery rows predate recipient FKs. Mapped PII must be read
    # through the model boundary; SQL equality would compare ciphertext.
    address = user.email.strip().lower()
    if getattr(user, "deletion_email_ciphertext", ""):
        from apps.makerspaces.secrets import decrypt_value
        address = decrypt_value(user.deletion_email_ciphertext).strip().lower()
    email_log = _model("integrations.EmailLog")
    from apps.accounts.models import User
    exclusive = address and not User.objects.exclude(pk=user.pk).filter(email__iexact=address).exists()
    if email_log is not None and exclusive:
        for row in email_log.objects.filter(recipient__isnull=True).exclude(makerspace__isnull=True).only(
            "makerspace_id", "to_email",
        ).iterator():
            if row.to_email.strip().lower() == address:
                result.add(row.makerspace_id)
    from apps.accounts.models_account_purge import AccountPurgeObject
    result.update(AccountPurgeObject.objects.filter(user=user).values_list("makerspace_id", flat=True))
    return result - {None}


def organization_ids(user):
    from apps.organizations.models import OrganizationMembership
    return set(OrganizationMembership.objects.filter(user=user).values_list("organization_id", flat=True))
