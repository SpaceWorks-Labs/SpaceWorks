"""Live personal audience/channel resolution; no inference from an email address."""
from dataclasses import dataclass

from apps.accounts import rbac
from apps.integrations.dispatch_policy import email_module_blocks
from apps.integrations.email_preferences import blocked_reason
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.notifications.models_preferences import NotificationPreference
from apps.notifications.preferences import mandatory_email, personal_enabled
from .notification_sources import source_eligible

LEGACY_STAFF_EMAIL_SOURCES = {
    "hardware_requests": {"hardware.request", "hardware.loan_reminder", "hardware.problem_report", "hardware.charge"},
    "printing": {"machines.service"},
    "maintenance": {"machines.maintenance"},
    "stock": {"machines.procurement"},
    "certifications": {"machines.certification", "machines.certification_summary"},
    "events": {"events.lifecycle"},
    "bookings": {"bookings.lifecycle"},
}


@dataclass(frozen=True)
class DeliveryTarget:
    channel: str
    endpoint: object = None


def policy_rows(model, space):
    return rbac.scope_notification_policy(model.objects.all(), makerspace_id=space.pk)


def eligible(envelope):
    from apps.makerspaces.servability import is_servable
    from apps.notifications.inbox import eligible_owner
    envelope.refresh_from_db()
    if not envelope.recipient_id:
        return False
    space = envelope.makerspace
    space.refresh_from_db()
    custody = envelope.stream == "backup" and envelope.event in {"archive_custody_alarm", "tenant_exit_custody_alarm"}
    owner_ok = eligible_owner(space, envelope.recipient_id)
    if mandatory_email(envelope.stream, envelope.event):
        from apps.accounts.models import User
        owner_ok = User.objects.filter(pk=envelope.recipient_id, is_active=True, access_status="active",
            is_tenant_dump_stub=False).exists() and not rbac.personal_notification_membership_refused(envelope.recipient, space.pk)
    if not is_servable(space, allow_archived=custody) or not owner_ok:
        return False
    if not source_eligible(envelope):
        return False
    from .recipients import feature_available
    if not custody and not mandatory_email(envelope.stream, envelope.event) and not feature_available(space, envelope.feature):
        return False
    if envelope.audience == "staff" and envelope.source_kind != "notification.digest":
        from .destinations import NotificationScope
        from .staff_notifications import staff_user_ids_for_feature
        return envelope.recipient_id in staff_user_ids_for_feature(
            space, envelope.feature, envelope.event, NotificationScope.from_dict(envelope.scope),
        )
    return True


def email_eligible(envelope):
    user = envelope.recipient
    user.refresh_from_db()
    if envelope.source_kind in {"bookings.lifecycle", "bookings.reminder"}:
        from apps.bookings.notification_owner_mailbox import email_reserved
        if email_reserved(envelope):
            return False
    verified = user.email_verified_at or legacy_staff_email_allowed(envelope)
    return bool(user.email and verified and not email_module_blocks(
        envelope.makerspace, envelope.stream, envelope.event,
    ) and not blocked_reason(envelope.makerspace, user.email, user_id=user.pk,
                            feature=envelope.feature, stream=envelope.stream, event=envelope.event))


def legacy_staff_email_allowed(envelope):
    """Only existing operational audiences may use an unverified staff mailbox."""
    if (envelope.audience != "staff" or envelope.source_kind not in LEGACY_STAFF_EMAIL_SOURCES.get(envelope.feature, set())
            or envelope.event in {"broadcast", "campaign"}):
        return False
    from .destinations import NotificationScope
    from .staff_notifications import staff_user_ids_for_feature
    from apps.makerspaces.models import MakerspaceMembership
    user = envelope.recipient
    membership = policy_rows(MakerspaceMembership, envelope.makerspace).select_related("assigned_role").filter(
        user=user, status="active", receives_notifications=True).first()
    return bool(user.is_active and user.access_status == "active" and not user.is_tenant_dump_stub
        and rbac.actions_for_membership(membership)
        and user.pk in staff_user_ids_for_feature(envelope.makerspace, envelope.feature,
            envelope.event, NotificationScope.from_dict(envelope.scope)))


def endpoint_eligible(endpoint, envelope):
    if endpoint is None:
        return False
    endpoint.refresh_from_db()
    config = endpoint.configuration
    config.refresh_from_db()
    return bool(endpoint.user_id == envelope.recipient_id
                and endpoint.makerspace_id == envelope.makerspace_id
                and endpoint.verification_state == "verified" and endpoint.verified_at
                and endpoint.consented_at and endpoint.revoked_at is None
                and config.enabled and config.personal_enabled
                and endpoint.provider == config.provider
                and endpoint.integration_generation == config.generation
                and endpoint.integration_identity == config.integration_identity)


def selected_policy(envelope):
    space, user = envelope.makerspace, envelope.recipient
    preference = policy_rows(NotificationPreference, space).filter(user=user, category=envelope.feature).first()
    if preference:
        return preference.channels, preference.email_fallback
    managers = rbac.effective_actions(user, space.pk) & {
        "manage_makerspace", "edit_inventory", "manage_machines", "manage_events", "manage_bookings",
    }
    telegram = policy_rows(NotificationEndpoint, space).filter(user=user, channel="telegram", revoked_at=None).first()
    if managers and endpoint_eligible(telegram, envelope):
        return ["telegram"], True
    if managers:
        return ["email"], True
    return ["email", "in_app"], True


def target_eligible(envelope, channel, endpoint=None):
    from .notification_catalog import is_notification_enabled, receipt_email_default
    config = policy_rows(ChannelConfiguration, envelope.makerspace).filter(channel=channel).first()
    configured_off = config is not None and not (config.enabled and config.personal_enabled)
    if channel == "email":
        mandatory = mandatory_email(envelope.stream, envelope.event)
        if configured_off and not mandatory:
            return False
        receipt = envelope.feature == "payments" and envelope.event == "payment_received" and receipt_email_default(envelope.makerspace)
        return email_eligible(envelope) and (mandatory or receipt or is_notification_enabled(envelope.makerspace, envelope.feature, channel))
    if configured_off or not personal_enabled(envelope.makerspace, envelope.recipient_id, envelope.feature, channel):
        return False
    if not is_notification_enabled(envelope.makerspace, envelope.feature, channel):
        return False
    if channel == "in_app":
        return module_enabled(envelope.makerspace, "notifications") and feature_enabled(envelope.makerspace, "notifications.member_inbox")
    if channel == "native_push":
        from .models_push import PushDevice
        from .push import push_configured
        return (feature_enabled(envelope.makerspace, "mobile.push") and push_configured()
                and PushDevice.objects.filter(makerspace=envelope.makerspace,
                    user_id=envelope.recipient_id, active=True, device_grant__status="active").exists())
    # External chat uses the existing notifications gate; WhatsApp has no new module key.
    from .dispatch_channels import channel_module_blocks
    if not module_enabled(envelope.makerspace, "notifications") or channel_module_blocks(envelope.makerspace, channel):
        return False
    from .notification_providers import provider_for
    return endpoint_eligible(endpoint, envelope) and provider_for(endpoint.configuration) is not None


def resolve(envelope, *, fallback=False):
    if not eligible(envelope):
        return []
    channels, allow_fallback = selected_policy(envelope)
    if envelope.stream == "account":
        channels = ["email"]  # mailbox authentication proofs never change mechanism
    if envelope.timing_policy == "digest" or envelope.source_kind == "notification.digest":
        channels = [channel for channel in channels if channel == "email"]
    targets = []
    for channel in channels:
        endpoint = None
        if channel not in ("email", "in_app", "native_push"):
            endpoint = policy_rows(NotificationEndpoint, envelope.makerspace).filter(
                user_id=envelope.recipient_id, channel=channel, revoked_at=None,
            ).first()
            bound = envelope.routing_snapshot.get(channel)
            if not endpoint or bound != {"id": endpoint.pk, "generation": endpoint.integration_generation,
                                          "provider": endpoint.provider, "identity": endpoint.integration_identity}:
                continue
        if target_eligible(envelope, channel, endpoint):
            targets.append(DeliveryTarget(channel, endpoint))
    mandatory = mandatory_email(envelope.stream, envelope.event)
    tenant = policy_rows(ChannelConfiguration, envelope.makerspace).filter(channel="email").first()
    may_fallback = allow_fallback and (tenant is None or tenant.email_fallback)
    if (mandatory or (may_fallback and (not targets or fallback))) and target_eligible(envelope, "email"):
        if not any(t.channel == "email" for t in targets):
            targets.append(DeliveryTarget("email"))
    return targets


def whatsapp_template(delivery, now=None):
    """Only authenticated inbound messages open the customer service window."""
    from .notification_wa_window import in_session_window
    from .models_endpoints import WhatsAppTemplate
    endpoint = delivery.endpoint
    if in_session_window(endpoint, now=now):
        return None
    return WhatsAppTemplate.objects.filter(configuration=endpoint.configuration,
        event=delivery.envelope.event, audience=delivery.envelope.audience,
        locale=delivery.envelope.context.get("locale", "en"), approved=True).first()
