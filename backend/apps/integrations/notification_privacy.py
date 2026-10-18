"""Account/tenant cleanup seams; sender protection and authenticated receipts survive."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models_cutover import NotificationCredentialVersion, NotificationIngress, NotificationLegacyMapping
from .models_contract import NotificationDelivery, NotificationEnvelope
from .models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge
from .models_messaging_settings import MessagingSenderIdentity
from .notification_cutover import guarded


@guarded(mutation=True)
@transaction.atomic
def prepare_channel_purge(makerspace, channel):
    """C calls before deleting channel/configuration/tenant rows, while its gate is held."""
    from .messaging.senders import retire_sender
    from .notification_sender import preserve_configuration
    for config in ChannelConfiguration.objects.filter(makerspace=makerspace, channel=channel):
        preserve_configuration(config, retired=True)
        config.enabled, config.personal_enabled, config.activation_hold = False, False, True
        config.save(update_fields=["enabled", "personal_enabled", "activation_hold"])
    NotificationCredentialVersion.objects.filter(makerspace_reference=makerspace.pk,
        configuration__channel=channel, retired_at=None).update(retired_at=timezone.now())
    for identity in MessagingSenderIdentity.objects.filter(makerspace=makerspace, channel=channel):
        retire_sender(identity)
        identity.makerspace = None
        identity.tenant_reference = makerspace.pk
        identity.save(update_fields=["makerspace", "tenant_reference"])
    # No phone/alias suppression or correlation/probe barrier is deleted here.


@guarded(mutation=True)
@transaction.atomic
def scrub_account(user, makerspace_id=None):
    """Use account IDs only: another account kind may share every contact field."""
    scope = {"makerspace_id": makerspace_id} if makerspace_id is not None else {}
    envelopes = NotificationEnvelope.objects.filter(recipient=user, **scope)
    owned_delivery_ids = NotificationDelivery.objects.filter(envelope__in=envelopes).values_list("pk", flat=True)
    NotificationDelivery.objects.filter(envelope__in=envelopes, state__in=["retrying", "held"]).update(
        state="skipped", retryable=False, last_error="account_removed", claim_until=None, next_attempt_at=None)
    for envelope in envelopes.select_for_update().iterator():
        envelope.message_body, envelope.context, envelope.routing_snapshot = "", {}, {}
        envelope.save(update_fields=["message_body", "context", "routing_snapshot"])
    proof_digests = set(NotificationEndpointChallenge.objects.filter(user=user, **scope).values_list("code_digest", flat=True))
    NotificationEndpointChallenge.objects.filter(user=user, **scope).delete()
    NotificationEndpoint.objects.filter(user=user, **scope, revoked_at=None).update(
        revoked_at=timezone.now(), verification_state="revoked")
    # Scrub only account-bound proofs. Provider facts and sender suppressions are
    # deployment history, shared with accounts/tenants using that physical sender.
    receipts = NotificationIngress.objects.filter(signed_user=user)
    if makerspace_id is not None:
        receipts = receipts.filter(Q(makerspace_reference=makerspace_id) | Q(makerspace_reference=None))
    for receipt in receipts:
        data = receipt.get_payload()
        proof = (data.get("event") or {}).get("proof")
        legacy_code = data.get("proof_code")
        if proof or legacy_code:
            from .notification_proofs import digest
            challenge_matches = receipt.signed_user_id == user.pk or digest(proof.get("code", "") if proof else legacy_code) in proof_digests
            if challenge_matches:
                if proof:
                    data["event"]["proof"] = None
                data["proof_code"], data["proof_user_id"], data["destination"] = "", None, ""
                receipt.signed_user = None
                receipt.set_payload(data)
                receipt.save(update_fields=["payload", "signed_user"])
        elif receipt.signed_user_id == user.pk:
            data["proof_user_id"] = None
            receipt.signed_user = None
            receipt.set_payload(data)
            receipt.save(update_fields=["payload", "signed_user"])
    from .models_messaging_consent import MessagingConsent
    from .models_messaging_delivery import MessagingDelivery
    consent_ids = MessagingConsent.objects.filter(user=user, **scope).values_list("pk", flat=True)
    old_delivery_ids = MessagingDelivery.objects.filter(user=user, **scope).values_list("pk", flat=True)
    NotificationLegacyMapping.objects.filter(
        Q(legacy_model="MessagingConsent", legacy_id__in=consent_ids)
        | Q(legacy_model="MessagingDelivery", legacy_id__in=old_delivery_ids)
        | Q(canonical_model="NotificationDelivery", canonical_id__in=owned_delivery_ids)).update(snapshot="")
    from apps.audit.services import record
    record(user, "notification.account_scrubbed", makerspace=envelopes.first().makerspace if envelopes.exists() else None,
        meta={"fields": ["message_body", "context", "routing_snapshot", "proof", "snapshot"]})


@guarded(mutation=True)
@transaction.atomic
def prepare_tenant_purge(makerspace):
    for channel in ("sms", "whatsapp"):
        prepare_channel_purge(makerspace, channel)
    NotificationLegacyMapping.objects.filter(makerspace=makerspace).update(snapshot="")
    for receipt in NotificationIngress.objects.filter(makerspace_reference=makerspace.pk):
        data = receipt.get_payload()
        if data.get("event"):
            data["event"]["proof"] = None
        data["proof_code"], data["proof_user_id"], data["destination"] = "", None, ""
        receipt.signed_user = None
        receipt.set_payload(data)
        receipt.save(update_fields=["payload", "signed_user"])
