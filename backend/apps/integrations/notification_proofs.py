"""Single-use provider proof, never a browser-supplied chat destination."""
from apps.integrations.notification_cutover import guarded
from datetime import timedelta
import secrets

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import Throttled, ValidationError

from apps.audit import services as audit
from .models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge
from .notification_providers import provider_for
from apps.tenant_migration.gate_runtime import tenant_write


def digest(code):
    return salted_hmac("notification.endpoint.proof.v1", code, algorithm="sha256").hexdigest()


@guarded(mutation=True)
def start(user, configuration, consent_version, *, phone_number=""):
    from .notification_api_access import contract_space
    contract_space(user, configuration.makerspace_id)
    import re
    if phone_number and not re.fullmatch(r"\+[1-9][0-9]{6,14}", phone_number):
        raise ValidationError({"phone_number": "Use an E.164 phone number."})
    now, code = timezone.now(), secrets.token_urlsafe(32)
    with tenant_write(configuration.makerspace_id), transaction.atomic():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(configuration.makerspace_id)
        from apps.accounts.models import User
        user = User.objects.select_for_update().get(pk=user.pk)
        config = ChannelConfiguration.objects.select_for_update().get(pk=configuration.pk)
        if phone_number and config.channel != "whatsapp":
            raise ValidationError({"phone_number": "Only WhatsApp accepts an unverified phone candidate."})
        if not config.enabled or not config.personal_enabled:
            raise ValidationError({"channel": "Personal delivery is disabled."})
        from .dispatch_channels import channel_module_blocks
        from apps.makerspaces.platform import module_enabled
        if channel_module_blocks(config.makerspace, config.channel) or (config.channel != "whatsapp" and not module_enabled(config.makerspace, "notifications")):
            raise ValidationError({"channel": "This notification module is disabled."})
        provider = provider_for(config)
        if provider is None or not hasattr(provider, "start_challenge"):
            raise ValidationError({"channel": "Account linking is unavailable for this provider."})
        recent = NotificationEndpointChallenge.objects.filter(makerspace=config.makerspace, user=user,
            created_at__gte=now - timedelta(hours=1))
        if recent.count() >= 5 or recent.filter(created_at__gte=now - timedelta(seconds=60)).exists():
            raise Throttled(wait=60)
        challenge = NotificationEndpointChallenge.objects.create(makerspace=config.makerspace, user=user,
            configuration=config, integration_generation=config.generation, integration_identity=config.integration_identity,
            code_digest=digest(code), expires_at=now + timedelta(minutes=10), consented_at=now,
            consent_version=consent_version, candidate_destination=phone_number)
        audit.record(user, "notification.endpoint_challenge_started", makerspace=config.makerspace,
                     target=challenge, meta={"channel": config.channel})
    # Provider I/O never holds the configuration lock.
    try:
        result = provider.start_challenge(challenge, code)
    except Exception:
        raise ValidationError({"channel": "The provider could not start verification."}) from None
    return challenge, result


@guarded(mutation=True)
def consume(configuration, proof, *, expected_user_id=None, expected_challenge_id=None):
    """Internal seam: proof MUST come from provider.verify_callback, never request JSON.

    Telegram adapters require private chat and bind chat.id + from.id; Slack validates
    workspace OIDC; Mattermost validates server OAuth; Discord validates identify OAuth;
    WhatsApp validates Twilio/Meta signatures and matching inbound sender/code.
    """
    from apps.encryption.write_fence import assert_mapped_write_allowed
    from .notification_whatsapp_consent import proof_observed_at
    now = timezone.now()
    observed_at = proof_observed_at() if configuration.channel == "whatsapp" else now
    with tenant_write(configuration.makerspace_id), transaction.atomic():
        assert_mapped_write_allowed(configuration.makerspace_id)
        if configuration.channel == "whatsapp":
            from .notification_sender import configuration_sender_key
            from .messaging.locks import lock_whatsapp_sender
            lock_whatsapp_sender(configuration_sender_key(configuration))
        from apps.accounts.models import User
        owner_rows = NotificationEndpointChallenge.objects.filter(configuration=configuration)
        owner_rows = (owner_rows.filter(pk=expected_challenge_id) if expected_challenge_id is not None
            else owner_rows.filter(code_digest=digest(proof.code)))
        owner_id = owner_rows.values_list("user_id", flat=True).first()
        if owner_id:
            User.objects.select_for_update().get(pk=owner_id)
        config = ChannelConfiguration.objects.select_for_update().get(pk=configuration.pk)
        challenges = NotificationEndpointChallenge.objects.select_for_update().filter(configuration=config)
        challenge = (challenges.filter(pk=expected_challenge_id) if expected_challenge_id is not None
                     else challenges.filter(code_digest=digest(proof.code))).first()
        if not challenge:
            raise ValidationError({"proof": "Invalid or expired proof."})
        valid = (constant_time_compare(challenge.code_digest, digest(proof.code))
                 and not challenge.consumed_at and challenge.created_at <= observed_at < challenge.expires_at
                 and challenge.attempts < 5
                 and challenge.integration_generation == config.generation
                 and challenge.integration_identity == config.integration_identity == proof.integration_identity
                 and (expected_user_id is None or expected_user_id == challenge.user_id)
                 and (expected_challenge_id is None or expected_challenge_id == challenge.pk)
                 and proof.private and proof.subject and proof.destination
                 and (not challenge.candidate_destination or challenge.candidate_destination == proof.destination)
                 and config.enabled and config.personal_enabled)
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        if valid:
            identity_digest = salted_hmac("notification.endpoint.identity.v1",
                f"{config.pk}:{config.generation}:{proof.subject}", algorithm="sha256").hexdigest()
            if NotificationEndpoint.objects.filter(configuration=config, identity_digest=identity_digest,
                    revoked_at=None, user=challenge.user).exists():
                valid = False
        if valid:
            from .recipients_owners import eligible_owner
            from apps.makerspaces.servability import is_servable
            from apps.makerspaces.platform import module_enabled
            from .dispatch_channels import channel_module_blocks
            valid = (eligible_owner(config.makerspace, challenge.user_id) and is_servable(config.makerspace)
                     and (config.channel == "whatsapp" or module_enabled(config.makerspace, "notifications"))
                     and not channel_module_blocks(config.makerspace, config.channel))
        if valid:
            NotificationEndpoint.objects.filter(makerspace=config.makerspace, user=challenge.user,
                channel=config.channel, revoked_at=None).update(revoked_at=now, verification_state="revoked")
            endpoint = NotificationEndpoint.objects.create(makerspace=config.makerspace, user=challenge.user,
                channel=config.channel, provider=config.provider, destination=proof.destination,
                provider_subject=proof.subject, identity_digest=identity_digest,
                configuration=config, integration_identity=config.integration_identity,
                integration_generation=config.generation, verified_at=now, consented_at=challenge.consented_at,
                consent_version=challenge.consent_version)
            challenge.consumed_at, challenge.endpoint = now, endpoint
            challenge.save(update_fields=["consumed_at", "endpoint"])
            if config.channel == "whatsapp":
                from .notification_whatsapp_consent import record_proof_consent
                record_proof_consent(config, endpoint)
            audit.record(challenge.user, "notification.endpoint_verified", makerspace=config.makerspace,
                         target=endpoint, meta={"channel": config.channel})
    # Raise outside atomic so failed attempts stay consumed.
    if not valid:
        raise ValidationError({"proof": "Invalid or expired proof."})
    return endpoint


def verified_callback(configuration, request, *, expected_user_id=None, expected_challenge_id=None):
    configuration.refresh_from_db()
    provider = provider_for(configuration)
    event = provider.verify_callback(request) if provider else None
    if event is None:
        raise ValidationError({"proof": "Provider verification failed."})
    return apply_verified_event(configuration, event, expected_user_id=expected_user_id,
        expected_challenge_id=expected_challenge_id)


@guarded(mutation=True)
def apply_verified_event(configuration, event, *, expected_user_id=None, expected_challenge_id=None):
    """Internal only: the event came from a verifier or the encrypted ingress journal."""
    if event.proof:
        endpoint = consume(configuration, event.proof, expected_user_id=expected_user_id,
                           expected_challenge_id=expected_challenge_id)
        if event.inbound:
            _destination_event(configuration, event, identity_digest=endpoint.identity_digest)
        return endpoint
    if expected_user_id is not None:
        raise ValidationError({"proof": "A verified account-link proof is required."})
    with tenant_write(configuration.makerspace_id), transaction.atomic():
        destination_changed = _destination_event(configuration, event)
        from .notification_delivery import apply_callback
        delivery_changed = apply_callback(configuration, event)
        return bool(delivery_changed or destination_changed)


def _destination_event(configuration, event, *, identity_digest=""):
    """A signed destination event applies to every account binding, atomically."""
    from .notification_destination_events import apply_destination_event
    return apply_destination_event(configuration, event, identity_digest=identity_digest)


@guarded(mutation=True)
def revoke(endpoint, *, actor):
    NotificationEndpoint.objects.filter(pk=endpoint.pk, revoked_at=None).update(
        revoked_at=timezone.now(), verification_state="revoked")
    audit.record(actor, "notification.endpoint_revoked", makerspace=endpoint.makerspace,
                 target=endpoint, meta={"channel": endpoint.channel})
