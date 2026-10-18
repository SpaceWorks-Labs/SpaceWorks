"""Current member consent snapshots, bound to canonical sender and account proof."""
from django.db.models import OuterRef, Subquery

from apps.accounts import rbac
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.models_messaging_consent import MessagingConsent
from apps.integrations.notification_resolution import endpoint_current
from apps.integrations.notification_sender import configuration_sender_key
from apps.makerspaces.models import MakerspaceMembership


def consented_members(space, channel):
    members = rbac.scope_notification_policy(MakerspaceMembership.objects.all(), makerspace_id=space.pk).filter(
        status="active", user__account_kind="member", user__is_active=True,
        user__access_status="active", user__is_tenant_dump_stub=False,
        user__retired_at=None, user__deletion_requested_at=None,
    ).values("user_id")
    config = ChannelConfiguration.objects.filter(makerspace=space, channel=channel).first()
    if config is None:
        return 0
    if channel == "whatsapp":
        # T signed endpoint proofs predate MessagingConsent. A missing annotation
        # cannot invent SMS consent, but a current signed WA proof is sufficient.
        latest = MessagingConsent.objects.filter(makerspace=space, channel=channel,
            user_id=OuterRef("user_id")).order_by("-pk")
        endpoints = NotificationEndpoint.objects.filter(makerspace=space, configuration=config,
            channel=channel, user_id__in=members).annotate(
                latest_action=Subquery(latest.values("action")[:1])).select_related("configuration")
        return len({row.user_id for row in endpoints.iterator()
                    if row.latest_action != "opted_out" and endpoint_current(row)})
    try:
        sender = configuration_sender_key(config)
    except Exception:
        return 0  # Broken sender identity cannot establish current consent.
    if not sender:
        return 0
    latest = MessagingConsent.objects.filter(makerspace=space, channel=channel,
        user_id=OuterRef("user_id")).order_by("-pk")
    consents = MessagingConsent.objects.filter(makerspace=space, channel=channel, user_id__in=members,
        pk=Subquery(latest.values("pk")[:1]), action="opted_in", sender_key=sender,
        configuration_generation=config.generation, phone_verified_at__isnull=False).select_related("user")
    # Compare mapped PII in memory: scoped ciphertext is not comparable in SQL.
    return sum(bool(row.user.phone_e164 and row.phone_e164 == row.user.phone_e164
                    and row.phone_verified_at == row.user.phone_verified_at) for row in consents.iterator())
