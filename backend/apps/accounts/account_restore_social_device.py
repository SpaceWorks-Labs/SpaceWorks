"""Restore-only native provider proof, anchored to one consumed app attestation."""

from apps.accounts.attestation import (
    consume_attestation_challenge, verify_attestation, AttestationRejected, AttestationUnavailable,
)
from apps.accounts.reauthentication_intents import ProviderUnavailable
from apps.accounts.social_jwt import SocialTokenError
from apps.accounts.social_nonces import provider_settings, native_apple_audience, SocialAuthUnavailable


def device_claims(row, *, nonce, id_token, challenge, attestation):
    try:
        anchor = consume_attestation_challenge(challenge, expected_id=row.attestation_challenge_id)
        if (anchor is None or not isinstance(attestation, dict) or not attestation
                or row.client_platform != ("ios" if anchor.platform == "apple" else "android")):
            raise SocialTokenError()
        verify_attestation(anchor, challenge, attestation)
        configuration, audience = provider_settings(row.provider, row.client_platform)
        if row.provider == "apple":
            from apps.accounts.social_apple import verify_apple_token
            audience = native_apple_audience(configuration, anchor)
            parser = verify_apple_token
        elif row.provider == "google":
            from apps.accounts.social_google import verify_google_token
            parser = verify_google_token
        else:
            raise SocialTokenError()
        if not audience:
            raise SocialTokenError()
        return parser(id_token, nonce=nonce, audience=audience)
    except (AttestationUnavailable, SocialAuthUnavailable) as exc:
        raise ProviderUnavailable() from exc
    except AttestationRejected as exc:
        raise SocialTokenError() from exc
