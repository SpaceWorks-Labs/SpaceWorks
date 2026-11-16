import pytest
from django.db import DatabaseError, connection, transaction

from apps.integrations.messaging.consent import grant_consent, live_consent
from apps.integrations.messaging.purge import archive_consents, purge_channel, purge_user
from apps.integrations.models import (
    MessagingConsent, MessagingDelivery, MessagingRecipientAlias, MessagingSuppression,
)
from tests.messaging.canonical_helpers import (
    OWN_SMS, envelope, platform_sms, platform_whatsapp, sms_channel, verified_endpoint, whatsapp_channel,
)

pytestmark = pytest.mark.django_db


def test_channel_purge_independent_and_shared_protection_retained(space, member, manager):
    from apps.integrations.messaging.protections import recipient_hash
    from apps.integrations.models import MessagingSenderIdentity
    from apps.integrations.models_contract import NotificationDelivery
    from apps.integrations.models_cutover import NotificationCredentialVersion
    from apps.integrations.models_endpoints import ChannelConfiguration
    platform_whatsapp()
    sms = sms_channel(space, manager, credentials=OWN_SMS)
    verified_endpoint(member, whatsapp_channel(space, manager))
    for channel, provider in (("sms", "twilio"), ("whatsapp", "meta")):
        grant_consent(user=member, makerspace_id=space.pk, channel=channel, action="opted_in")
        intent = envelope(space, member, key="purge-" + channel)
        NotificationDelivery.objects.create(makerspace=space, envelope=intent, channel=channel,
                                            target_key=channel, provider=provider)
    phone = recipient_hash("phone", member.phone_e164)
    MessagingSuppression.objects.create(channel="sms", sender_key="platform", recipient_hash=phone, reason="inbound_stop")
    MessagingRecipientAlias.objects.create(channel="whatsapp", sender_key="platform", phone_hash=phone, alias_hash="alias")
    purge_channel(space, "sms")
    assert set(ChannelConfiguration.objects.filter(makerspace=space).values_list("channel", flat=True)) == {"whatsapp"}
    assert set(MessagingConsent.objects.values_list("channel", flat=True)) == {"whatsapp"}
    assert set(NotificationDelivery.objects.values_list("channel", flat=True)) == {"whatsapp"}
    # Shared physical protection and retired callback verifiers outlive the channel.
    assert MessagingSuppression.objects.count() == MessagingRecipientAlias.objects.count() == 1
    assert NotificationCredentialVersion.objects.filter(configuration_reference=sms.pk,
                                                        retired_at__isnull=False).exists()
    identity = MessagingSenderIdentity.objects.get(sender_key=sms.sender_key)
    assert not identity.active and identity.makerspace_id is None and identity.tenant_reference == space.pk


def test_archive_appends_optout_restore_does_not_restore_consent_and_purge_deletes_history(space, member):
    platform_sms()
    sms_channel(space)
    grant_consent(user=member, makerspace_id=space.pk, channel="sms", action="opted_in")
    with transaction.atomic():
        archive_consents(member, [space])
    assert not live_consent(space, member, "sms")
    assert MessagingConsent.objects.latest("id").source == "account_archive"
    assert MessagingConsent.objects.count() == 2
    MessagingDelivery.objects.create(makerspace=space, user=member, channel="sms", audience="member",
                                     feature="bookings", event="created", event_key="booking:1")
    with transaction.atomic():
        purge_user(member, space.pk)
    assert not MessagingConsent.objects.filter(user=member).exists()
    assert not MessagingDelivery.objects.filter(user=member).exists()


def test_consent_ownership_discovered_and_personal_export_selector_is_exact(space, member):
    from apps.accounts.account_deletion_discovery import tenant_ids
    from apps.data_export.subject_selectors import subject_query
    platform_sms()
    sms_channel(space)
    grant_consent(user=member, makerspace_id=space.pk, channel="sms", action="opted_in")
    assert space.pk in tenant_ids(member)
    assert subject_query(MessagingConsent, member, space.pk).count() == 1


def test_pii_maintenance_requires_registered_operation_and_cannot_change_history(space, member):
    from apps.encryption.models import PiiMakerspaceWriteFence
    from apps.encryption.write_fence import fence_operation
    from uuid import uuid4
    platform_sms()
    sms_channel(space)
    grant_consent(user=member, makerspace_id=space.pk, channel="sms", action="opted_in")
    row = MessagingConsent.objects.get(user=member)
    operation = uuid4()
    fence = PiiMakerspaceWriteFence.objects.get(makerspace=space)
    fence.state, fence.operation_id, fence.operation_kind = "closed", operation, "enable_transition"
    fence.save(update_fields=["state", "operation_id", "operation_kind"])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE integrations_messagingconsent SET phone_e164='replacement' WHERE id=%s", [row.pk])
    with transaction.atomic(), fence_operation(operation), connection.cursor() as cursor:
        # Represents envelope rewrapping/backfill; only the mapped column can change.
        cursor.execute("UPDATE integrations_messagingconsent SET phone_e164=%s WHERE id=%s", [member.phone_e164, row.pk])
    with pytest.raises(DatabaseError), transaction.atomic(), fence_operation(operation), connection.cursor() as cursor:
        cursor.execute("UPDATE integrations_messagingconsent SET source='inbound_stop' WHERE id=%s", [row.pk])


def test_export_and_separability_declarations():
    from apps.data_export.guards import (
        validate_credentials, validate_dataset_contract, validate_model_and_field_coverage,
        validate_semantic_references, validate_user_edges, validate_user_projection,
    )
    from apps.separability.registry import pii_fields_for, purge_plan_for
    # Exercise the complete export contract here. The aggregate validate_all also
    # checks unrelated migration audit-ID paths, covered by its own registry tests.
    validate_model_and_field_coverage()
    validate_dataset_contract()
    validate_user_edges()
    validate_semantic_references()
    validate_credentials()
    validate_user_projection()
    assert {field.field_name for field in pii_fields_for("integrations.MessagingConsent")} == {"phone_e164"}
    assert purge_plan_for("sms").delete != purge_plan_for("whatsapp").delete


def test_purging_one_tenant_on_platform_sender_preserves_the_other(space, member):
    from apps.integrations.models import PlatformSmsSettings, MessagingSenderIdentity
    from apps.integrations.messaging.protections import recipient_hash
    from apps.makerspaces.models import Makerspace
    from tests.fixed_roles.helpers import assign_builtin_roles
    other = Makerspace.objects.create(name="Other messaging tenant", slug="other-messaging-tenant")
    assign_builtin_roles(member, other, "member")
    platform = platform_sms(token="platform-token")
    key = "twilio:" + platform.account_sid + ":" + platform.notifications_from_number
    for tenant in (space, other):
        sms_channel(tenant)  # Each tenant explicitly opts in to the shared platform sender.
        grant_consent(user=member, makerspace_id=tenant.pk, channel="sms", action="opted_in")
    suppression = MessagingSuppression.objects.create(channel="sms", sender_key=key,
        recipient_hash=recipient_hash("phone", member.phone_e164), reason="inbound_stop")
    purge_channel(space, "sms")
    assert MessagingConsent.objects.filter(makerspace=other).count() == 1
    assert MessagingSuppression.objects.filter(pk=suppression.pk).exists()
    assert MessagingSenderIdentity.objects.filter(owner="platform", sender_key=key, active=True).exists()
    assert PlatformSmsSettings.objects.get(pk=1).get_auth_token() == "platform-token"
