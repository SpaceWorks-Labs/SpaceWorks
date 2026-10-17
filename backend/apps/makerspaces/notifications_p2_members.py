"""Membership lifecycle intents with explicit owners and live source checks."""
from django.utils import timezone

from apps.accounts import rbac
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.email_templates_fablab import membership_context
from apps.operations.notifications_p2 import body, direct_mail_unless_routed, fanout, revision, safe_notification, scoped, staff_link, template
from .models import MakerspaceMembership, MembershipRequest
from .platform import feature_enabled

MEMBERSHIP = "membership.lifecycle"
REQUEST = "membership.application"
PERSONAL_EVENTS = {"joined", "verified", "cancelled"}
REQUEST_EVENTS = {"request_pending": {"requested", "awaiting_vouches"},
                  "declined": {"revoked"}, "awaiting_payment": {"awaiting_payment"},
                  "payment_due": {"awaiting_payment"}, "invitation": {"invited"}}


def member_revision(row, event):
    return revision(row.pk, row.activated_at or row.created_at,
        row.verified_at if event == "verified" else None,
        row.renewal_cancelled_at if event == "cancelled" else None)


def request_revision(row, event):
    if event == "request_pending":
        # Requested -> awaiting_vouches is still the same pending application,
        # and often happens later in the SAME domain transaction.
        return revision(row.pk, row.created_at, "pending")
    return revision(row.pk, row.state, row.updated_at)


def _member(envelope):
    return scoped(MakerspaceMembership, envelope.makerspace_id).select_related(
        "user", "makerspace", "activated_by", "verified_by",
    ).filter(pk=envelope.source_id).first()


def _request(envelope):
    return scoped(MembershipRequest, envelope.makerspace_id).select_related(
        "user", "makerspace", "invited_by", "decided_by",
    ).filter(pk=envelope.source_id).first()


def reapplication_owner_eligible(envelope):
    """A revoked member still owns their fresh admission, never their old access."""
    if envelope.audience not in {"member", "requester"}:
        return False
    row = _request(envelope)
    if (row is None or row.kind != "request" or row.user_id != envelope.recipient_id
            or row.requested_by_id != envelope.recipient_id or not request_eligible(envelope)):
        return False
    user = row.user
    if not user.is_active or user.access_status != "active" or user.is_tenant_dump_stub:
        return False
    membership = scoped(MakerspaceMembership, row.makerspace_id).filter(user=user).first()
    return bool(membership and membership.status == "revoked" and membership.receives_notifications
                and row.created_at >= (membership.revoked_at or membership.created_at))


def activation_authorized(row):
    actor = row.activated_by
    if actor and actor.pk == row.user_id:
        return actor.is_active and actor.access_status == "active"
    if actor and rbac.can(actor, rbac.Action.MANAGE_MEMBERS, row.makerspace_id):
        return True
    # A payment webhook can finish an admission approved earlier by staff (or
    # eligible vouchers). Its system actor is deliberately null.
    requests = scoped(MembershipRequest, row.makerspace_id).filter(
        user_id=row.user_id, state="active", approved_at__isnull=False,
    ).select_related("approved_by")
    for request in requests:
        if request.approved_by and rbac.can(request.approved_by, rbac.Action.MANAGE_MEMBERS, row.makerspace_id):
            return True
        from .membership_admission_settings import settings_for
        from .membership_vouching import valid_vouches
        policy = settings_for(row.makerspace)
        if policy.vouch_replaces_approval and valid_vouches(request, policy).count() >= policy.vouches_required:
            return True
    return False


def member_eligible(envelope):
    row = _member(envelope)
    if row is None or row.status != "active" or envelope.event not in PERSONAL_EVENTS | {"member_joined", "approved"}:
        return False
    proof_id = envelope.context.get("verification_id")
    expected = revision(row.pk, proof_id) if envelope.event == "verified" else member_revision(row, envelope.event)
    if envelope.revision != expected:
        return False
    if envelope.audience != "staff" and row.user_id != envelope.recipient_id:
        return False
    if envelope.event == "verified":
        from apps.audit.models import AuditLog
        proof = scoped(AuditLog, row.makerspace_id).select_related("actor").filter(
            pk=proof_id, action="membership.verified", target_type=row._meta.label_lower,
            target_id=str(row.pk),
        ).first()
        if proof is None or scoped(AuditLog, row.makerspace_id).filter(
            action="membership.unverified", target_type=row._meta.label_lower,
            target_id=str(row.pk), pk__gt=proof.pk,
        ).exists():
            return False
        verifier = proof.actor
        delegated = scoped(MakerspaceMembership, row.makerspace_id).filter(
            user=verifier, status="active", can_verify=True,
            user__is_active=True, user__access_status="active",
        ).exists() if verifier else False
        return bool(row.verified_at and verifier and (
            rbac.can(verifier, rbac.Action.MANAGE_MEMBERS, row.makerspace_id) or delegated))
    if envelope.event == "approved":
        return activation_authorized(row)
    if envelope.event == "cancelled":
        return bool(row.renewal_cancelled_at and feature_enabled(row.makerspace, "membership.lifecycle_mail"))
    return activation_authorized(row)


def request_eligible(envelope):
    row = _request(envelope)
    if row is None or row.state not in REQUEST_EVENTS.get(envelope.event, set()):
        return False
    if envelope.revision != request_revision(row, envelope.event):
        return False
    if envelope.audience != "staff" and row.user_id != envelope.recipient_id:
        return False
    if row.expires_at and envelope.event != "declined" and row.expires_at <= timezone.now():
        return False
    if envelope.event == "declined":
        return bool(row.decided_by and rbac.can(row.decided_by, rbac.Action.MANAGE_MEMBERS, row.makerspace_id))
    if envelope.event == "invitation":
        actor = row.invited_by
        if actor is None or not actor.is_active or actor.access_status != "active":
            return False
        action = rbac.Action.MANAGE_MAKERSPACE if row.assigned_role and row.assigned_role.granted_actions else rbac.Action.MANAGE_MEMBERS
        if rbac.can(actor, action, row.makerspace_id):
            return True
        return scoped(MakerspaceMembership, row.makerspace_id).filter(
            user=actor, status="active", can_refer=True,
        ).exists() and row.makerspace.referrals_enabled
    if envelope.event in {"awaiting_payment", "payment_due"}:
        from apps.payments.models import Payment
        return bool(row.admission_payment_id and scoped(Payment, row.makerspace_id).filter(
            pk=row.admission_payment_id, status="pending", member_id=row.user_id,
            subject_type="membership_request", subject_id=row.pk,
        ).exists())
    return True


def member_body(row, event, audience):
    link = f"/m/{row.makerspace.slug}/member"
    if audience == "staff":
        if event == "member_joined":
            return template(row.makerspace, "membership", audience, event,
                membership_context(row.makerspace, event, user=row.user), link=staff_link(row.makerspace, "members"))
        if event == "approved":
            return template(row.makerspace, "membership", audience, event,
                {"makerspace": bag(name=row.makerspace.name), "event_name": event,
                 "subject": bag(id=row.pk, status=row.status)}, link=staff_link(row.makerspace, "members"))
        return body("Membership update", f"Membership #{row.pk}: {event.replace('_', ' ')}.", staff_link(row.makerspace, "members"))
    if event in {"approved", "joined"}:
        return body(f"Welcome to {row.makerspace.name}",
                    f"Your membership at {row.makerspace.name} is active. Welcome!", link)
    if event == "verified":
        return body(f"You are verified at {row.makerspace.name}",
                    f"You have been verified as a member of {row.makerspace.name}.", link)
    return body("Membership update", f"Your membership at {row.makerspace.name}: {event.replace('_', ' ')}.", link)


def request_body(row, event, audience):
    if event == "request_pending":
        return template(row.makerspace, "membership", audience, event,
            membership_context(row.makerspace, event, request=row),
            link=staff_link(row.makerspace, "members") if audience == "staff" else f"/m/{row.makerspace.slug}/member")
    if event in {"declined", "awaiting_payment", "payment_due"}:
        return template(row.makerspace, "membership", audience, event,
            {"makerspace": bag(name=row.makerspace.name), "event_name": event,
             "subject": bag(id=row.pk, status=row.state)},
            link=staff_link(row.makerspace, "members") if audience == "staff" else f"/m/{row.makerspace.slug}/member")
    if audience == "staff":
        return body("Membership application update", f"Membership application #{row.pk}: {event.replace('_', ' ')}.", staff_link(row.makerspace, "members"))
    text = ("You have been invited to join this makerspace. Sign in to review the invitation."
            if event == "invitation" else f"Your membership application at {row.makerspace.name}: {event.replace('_', ' ')}.")
    return body("Membership update", text, f"/m/{row.makerspace.slug}/member")


def render_member(envelope):
    return member_body(_member(envelope), envelope.event, envelope.audience)


def render_request(envelope):
    return request_body(_request(envelope), envelope.event, envelope.audience)


@safe_notification
def notify_member(row, event, *, owner=True, staff=True):
    if event == "cancelled" and not feature_enabled(row.makerspace, "membership.lifecycle_mail"):
        return
    proof_id = None
    if event == "verified":
        from apps.audit.models import AuditLog
        proof_id = scoped(AuditLog, row.makerspace_id).filter(
            action="membership.verified", target_type=row._meta.label_lower, target_id=str(row.pk),
        ).order_by("-pk").values_list("pk", flat=True).first()
        if proof_id is None:
            raise ValueError("Member verification requires its audit event")
    version = revision(row.pk, proof_id) if proof_id else member_revision(row, event)
    result = fanout(row=row, space=row.makerspace, feature="members", stream="membership", event=event,
        source_kind=MEMBERSHIP, revision=version,
        owner=row.user if owner else None, owner_body=member_body(row, event, "requester"),
        staff_body=member_body(row, event, "staff"), staff=staff, context={"verification_id": proof_id},
        staff_context=membership_context(row.makerspace, event, user=row.user) if event == "member_joined" else
            {"makerspace": bag(name=row.makerspace.name), "event_name": event,
             "subject": bag(id=row.pk, status=row.status)})
    if owner and event in {"approved", "joined", "verified"}:
        # Welcome and verification mail were direct, not matrix-governed.
        own = member_body(row, event, "requester")
        direct_mail_unless_routed(space=row.makerspace, source_kind=MEMBERSHIP, row=row, revision=version,
            event=event, owner=row.user, to_email=(row.user.email or "").strip(), subject=own["subject"],
            text=own["text"], stream="membership", audience="member", feature="members")
    return result


@safe_notification
def notify_request(row, event):
    return fanout(row=row, space=row.makerspace, feature="members", stream="membership", event=event,
        source_kind=REQUEST, revision=request_revision(row, event), owner=row.user,
        owner_body=request_body(row, event, "requester"), staff_body=request_body(row, event, "staff"),
        staff=event != "invitation", staff_context=membership_context(row.makerspace, event, request=row)
        if event == "request_pending" else {"makerspace": bag(name=row.makerspace.name), "event_name": event,
                                          "subject": bag(id=row.pk, status=row.state)})


@safe_notification
def notify_invitation(row):
    # Only the explicit account link can receive personal chat; an unclaimed
    # invitation keeps the existing email/share path and carries no chat bearer.
    if row.user_id and row.user.email_verified_at:
        result = notify_request(row, "invitation")
        # The invitation email was always sent; keep it unless the envelope emails.
        direct_mail_unless_routed(space=row.makerspace, source_kind=REQUEST, row=row,
            revision=request_revision(row, "invitation"), event="invitation", owner=row.user,
            to_email=row.invite_email, subject="Makerspace membership invitation",
            text="You have been invited to join this makerspace. Sign in with this email to claim the invitation.",
            stream="membership", audience="member", feature="", address_owner=False)
        return result
    from apps.integrations.email import send_makerspace_email
    return send_makerspace_email(row.makerspace, "Makerspace membership invitation",
        "You have been invited to join this makerspace. Sign in with this email to claim the invitation.",
        [row.invite_email], stream="membership", event="invitation", audience="member")


def register():
    register_source(MEMBERSHIP, NotificationSource(member_eligible, render_member))
    register_source(REQUEST, NotificationSource(request_eligible, render_request))
