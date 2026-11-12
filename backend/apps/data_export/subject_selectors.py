"""Subject ownership, layered over the reviewed tenant dataset registry.

These are row selectors, never a second column allowlist. Authorship is deliberately
not ownership: a staff member who handles somebody's loan cannot export that loan.
Unlisted tenant configuration and anonymous records have no proven subject binding.
"""

from django.apps import apps
from django.db.models import Q

from apps.accounts import rbac
from apps.accounts.staff_identity import actor_ids_for
from apps.backup.capture_managers import every_row

from .datasets import DATASET_SPECS


SUBJECT_PATHS = {
    "events.EventBookingDecision": ("creator",),
    "events.EventConsumablePlanContext": ("plan__borrower",),
    "bookings.BookingConsumablePlanContext": ("plan__borrower",),
    "inventory.EquipmentConsumablePlan": ("borrower",),
    "inventory.EquipmentKitAllocation": ("request__requester",),
    "inventory.EquipmentProposalReceipt": ("borrower",),
    "events.EventLoanContext": ("request__requester",),
    "bookings.BookingLoanContext": ("request__requester",),
    "makerspaces.GuestPass": ("holder",),  # decision 223: the holder's own passes
    "integrations.NotificationEnvelope": ("recipient",),
    "integrations.NotificationDelivery": ("envelope__recipient",),
    "integrations.NotificationEndpoint": ("user",),
    "notifications.NotificationPreference": ("user",),
    "notifications.MemberNotificationPreference": ("user",),
    "presence.PresencePreference": ("account",),
    "makerspaces.PublicHandle": ("user",),
    "makerspaces.ProfileTimelineEntry": ("profile__membership__user",),
    "integrations.MessagingConsent": ("user",),
    "integrations.MessagingDelivery": ("user",),
    "accounts.DeviceActivityDay": ("grant__user",),
    "accounts.WebSessionActivityDay": ("user",),
    "notifications.MemberPushDelivery": ("envelope_delivery__envelope__recipient",),
    "integrations.PushDeliveryAttempt": ("recipient",),
    "operations.SavedView": ("owner",),
    "apiclients.ApiKeyRequest": ("requester",),
    "bookings.BookingCheckInEvent": ("booking__member",),
    "bookings.Booking": ("member",),
    "devices.PrinterJob": ("service_request__member",),
    "devices.PrinterJobConsumption": ("job__service_request__member",),
    "boxes.BoxScan": ("request__requester",),
    "boxes.QrScanEvent": ("request__requester",),
    "events.EventRegistration": ("member",),
    "events.EventCheckInEvent": ("registration__member",),
    "events.EventFeedbackResponse": ("registration__member",),
    "events.EventAttendanceCertificate": ("recipient_member",),
    "evidence.EvidencePhoto": ("uploaded_by",),
    "evidence.EvidenceObjectRetentionState": ("evidence__uploaded_by",),
    "hardware_requests.HardwareRequest": ("requester",),
    "hardware_requests.HardwareRequestItem": ("request__requester",),
    "hardware_requests.HardwareRequestItemAsset": ("request_item__request__requester",),
    "hardware_requests.PublicProblemReport": ("requester",),
    "hardware_requests.PublicToolLoan": ("requester",),
    "hardware_requests.RequesterAccountability": ("requester",),
    "hardware_requests.ReturnEvent": ("request__requester",),
    "integrations.NotificationRecipient": ("user",),
    "machines.MachineOperator": ("user",),
    "machines.MachineServiceRequest": ("member",),
    "machines.MachineUsageEntry": ("service_request__member", "member"),
    "machines.CertificationGrant": ("membership__user",),
    "machines.GuestCertificationGrant": ("user",),  # final audit m22 (L3a): the grantee's own certification
    "machines.MachineAccessGrant": ("member",),  # decision 319: the member's own machine access
    "machines.SupervisedParticipant": ("user",),
    "machines.SupervisedUse": ("user",),
    "maintenance.Incident": ("involved_user", "sponsor_user"),  # not the reporter: authorship is not ownership
    "machines.ServiceRequestFile": ("owner_user",),
    "machines.ServiceRequestConsumption": ("service_request__member",),
    "makerspaces.MakerspaceMembership": ("user",),
    "makerspaces.MemberCard": ("membership__user",),
    # Decision 345(b): the member's own background-eraser opt-out (a privacy choice) for the card that owns the photo.
    "card_designs.CardPhotoEraserOptOut": ("member_card__membership__user", "programme_card__user", "event_card__person"),
    "makerspaces.MemberProfile": ("membership__user",),
    "makerspaces.MemberProject": ("profile__membership__user",),
    "makerspaces.MembershipRequest": ("user",),
    "makerspaces.MembershipVouch": ("request__user",),
    "makerspaces.MembershipTerm": ("membership__user",),
    "payments.Payment": ("member",),
    "payments.ManualSettlement": ("payment__member",),
    "payments.Refund": ("payment__member",),
    "payments.RefundCase": ("payment__member",),
    "presence.PresenceSession": ("member",),
}
from apps.tenant_migration.catalog_p2_bookings import SUBJECT_PATHS as _P2_BOOKING_SUBJECTS
SUBJECT_PATHS.update(_P2_BOOKING_SUBJECTS)
from .classification_l3b import SUBJECT_PATHS as _L3B_SUBJECTS  # noqa: E402
SUBJECT_PATHS.update(_L3B_SUBJECTS)


def subject_query(model, user, makerspace_id):
    label = model._meta.label
    from .subject_runtime import RUNTIME_FIELDS, runtime_subject_query
    if label in RUNTIME_FIELDS:
        return runtime_subject_query(model, user, makerspace_id)
    if label == "accounts.User":
        return every_row(model).filter(pk=user.pk, retired_at__isnull=True)
    # History recorded against a shell merged into this person is theirs too.
    ids = actor_ids_for(user)
    if label == "audit.AuditLog":
        own = Q(actor_id__in=ids) | Q(
            target_type="accounts.user", target_id__in=[str(pk) for pk in ids],
        )
        # Both tracks: a person's staff role in this space is their own record too.
        memberships = rbac.scope_by_makerspace(
            user, every_row(apps.get_model("makerspaces.MakerspaceMembership")).filter(user_id__in=ids),
        ).filter(makerspace_id=makerspace_id)
        own |= Q(
            target_type="makerspaces.makerspacemembership",
            target_id__in=[str(pk) for pk in memberships.values_list("pk", flat=True)],
        )
    else:
        paths = SUBJECT_PATHS.get(label)
        if not paths:
            return every_row(model).none()
        own = Q()
        for path in paths:
            own |= Q(**{f"{path}_id__in": ids})
    predicate = DATASET_SPECS[label][1]
    query = every_row(model).filter(own).filter(predicate.as_q(makerspace_id))
    # An explicit tenant intersection remains required even for a superadmin.
    return rbac.scope_by_makerspace(queryset=query, actor=user,
                                   makerspace_field=predicate.any_paths[0] + "_id")
