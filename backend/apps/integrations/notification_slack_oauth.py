"""OAuth state uses the frozen durable challenge, bound to actor/tenant/generation."""
import base64
import hashlib
from datetime import timedelta
import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import ValidationError, Throttled

from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, NotificationEndpointChallenge
from .notification_proofs import digest

SALT = "notification.chat.oauth.v1"


def redirect_uri(channel, makerspace_id=None, challenge_id=None):
    # Registered URIs must match byte for byte. Dynamic bindings live in state.
    value = getattr(settings, f"NOTIFICATION_{channel.upper()}_REDIRECT_URI", "")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.fragment or "{" in value or "}" in value):
        raise ValidationError({"channel": "Configure an HTTPS OAuth redirect URI on the server."})
    return value


def state_for(challenge, code, *, purpose="link"):
    # Bindings live in the durable row; keep state below the frozen API's 512-char bound.
    return signing.dumps({"challenge": challenge.pk, "purpose": purpose, "code": code}, salt=SALT)


def read_state(config, state, *, purpose="link", user_id=None, challenge_id=None):
    try:
        value = signing.loads(state, salt=SALT, max_age=600)
        challenge = NotificationEndpointChallenge.objects.select_related("user").get(
            pk=value["challenge"], configuration=config, makerspace_id=config.makerspace_id)
        if (value["purpose"] != purpose
                or user_id is not None and user_id != challenge.user_id
                or challenge_id is not None and challenge_id != challenge.pk
                or challenge.integration_generation != config.generation
                or challenge.integration_identity != config.integration_identity
                or challenge.consumed_at or challenge.expires_at <= timezone.now()
                or challenge.attempts >= 5
                or not constant_time_compare(challenge.code_digest, digest(value["code"]))
                or (challenge.consent_version == "slack-install") != (purpose == "install")):
            raise ValueError()
        return challenge, value["code"]
    except (signing.BadSignature, KeyError, TypeError, ValueError, NotificationEndpointChallenge.DoesNotExist):
        raise ValidationError({"proof": "Invalid or expired OAuth state."}) from None


def verifier(code):
    # Never store a PKCE secret in a URL or plaintext database column.
    return salted_hmac("notification.chat.pkce.v1", code, algorithm="sha256").hexdigest()


def pkce(code):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier(code).encode()).digest()).decode().rstrip("=")


def install_challenge(user, config):
    now, code = timezone.now(), secrets.token_urlsafe(32)
    with tenant_write(config.makerspace_id), transaction.atomic():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(config.makerspace_id)
        config = ChannelConfiguration.objects.select_for_update().get(pk=config.pk)
        recent = NotificationEndpointChallenge.objects.filter(user=user, configuration=config,
            created_at__gte=now - timedelta(hours=1))
        if recent.count() >= 5 or recent.filter(created_at__gte=now - timedelta(seconds=60)).exists():
            raise Throttled(wait=60)
        challenge = NotificationEndpointChallenge.objects.create(user=user, makerspace_id=config.makerspace_id,
            configuration=config, integration_generation=config.generation,
            integration_identity=config.integration_identity, code_digest=digest(code),
            expires_at=now + timedelta(minutes=10), consented_at=now, consent_version="slack-install")
        audit.record(user, "notification.chat_install_started", makerspace=config.makerspace,
            target=challenge, meta={"channel": "slack"})
    return challenge, code


def claim_install(config, state):
    challenge, _ = read_state(config, state, purpose="install")
    from .notification_api_access import contract_space
    contract_space(challenge.user, config.makerspace_id, manager=True)
    with tenant_write(config.makerspace_id), transaction.atomic():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(config.makerspace_id)
        locked = ChannelConfiguration.objects.select_for_update().get(pk=config.pk)
        if locked.generation != config.generation:
            raise ValidationError({"proof": "Configuration changed; restart installation."})
        challenge, _ = read_state(config, state, purpose="install")
        challenge = NotificationEndpointChallenge.objects.select_for_update().get(pk=challenge.pk)
        if challenge.consumed_at:
            raise ValidationError({"proof": "OAuth state already consumed."})
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
        audit.record(challenge.user, "notification.chat_install_state_consumed", makerspace=config.makerspace,
            target=challenge, meta={"channel": "slack"})
    return challenge.user


def save_install(config, user, credentials, identity):
    if not isinstance(identity, str) or not 1 <= len(identity) <= 255:
        raise ValidationError({"channel": "Provider returned an invalid installation identity."})
    from .notification_api_access import contract_space
    contract_space(user, config.makerspace_id, manager=True)
    with tenant_write(config.makerspace_id), transaction.atomic():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(config.makerspace_id)
        row = ChannelConfiguration.objects.select_for_update().get(pk=config.pk)
        if row.generation != config.generation:
            raise ValidationError({"channel": "Configuration changed; restart installation."})
        row.set_credentials(credentials)
        row.integration_identity = identity
        row.generation += 1
        row.save(update_fields=["credentials", "integration_identity", "generation", "updated_at"])
        audit.record(user, "notification.channel_configured", makerspace=config.makerspace,
            target=row, meta={"channel": config.channel, "generation": row.generation})
    return row
