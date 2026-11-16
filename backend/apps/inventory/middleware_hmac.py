from django.utils.translation import gettext
import hashlib
import hmac
import logging
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.exceptions import NotFound
from apps.apiclients import telemetry
from apps.apiclients.read_prefixes import requires_signed_read
from apps.apiclients.crypto import decrypt_secret
from apps.inventory.middleware_nonce import (
    NONCE_MAX_LENGTH,
    body_could_re_encode_nonce,
    claim_nonce,
    nonce_is_valid,
)
from apps.inventory.middleware_observability import (
    BAD_SIGNATURE,
    NONCE_MISSING,
    NONCE_REPLAY,
    NONCE_STORE_UNAVAILABLE,
    NO_CREDENTIALS,
    ORIGIN_DENIED,
    SKEW,
    UNKNOWN_CLIENT,
    WOULD_REJECT_EVENT as WOULD_REJECT_EVENT,
    log_would_reject,
    failure_reason,
    set_failure_reason,
)

logger = logging.getLogger("apps.inventory.middleware")
LEGACY_NONCE_WARNING_EVENT = "api_client_nonce_missing_legacy"
AMBIGUOUS_NONCE_BODY_EVENT = "api_client_nonce_ambiguous_body"


from apps.inventory.middleware_publishable import PublishableKeyMixin
from apps.inventory.middleware_hmac_scope import ClientScopeMixin
from config.redis_cache import SharedCacheUnavailable


class FrontendHMACMiddleware(PublishableKeyMixin, ClientScopeMixin):
    """Validate signed client requests for protected API paths using the ApiClient registry."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_valid = True
        if self._is_protected_path(request):
            is_valid = self._is_valid(request)
            if not is_valid and not settings.API_CLIENT_AUTH_REQUIRED:
                log_would_reject(request)
        if self._should_reject_invalid(request) and not is_valid:
            if getattr(request, "_api_client_signed_target_hidden", False):
                response = JsonResponse({"detail": str(NotFound().detail), "code": "not_found"}, status=404)
                response["Cache-Control"] = "private, no-store"
                response["Referrer-Policy"] = "no-referrer"
                return response
            if failure_reason(request) == NONCE_STORE_UNAVAILABLE:
                # The signature was good; the replay guard could not be consulted. Retryable,
                # and never accepted unproven (decision 339).
                response = JsonResponse({"detail": gettext("Signed requests are briefly unavailable. Retry shortly."),
                                         "code": "replay_guard_unavailable"}, status=503)
                response["Retry-After"] = "5"
                return response
            return JsonResponse({"detail": gettext("Invalid client signature.")}, status=401)
        return self.get_response(request)

    def _should_reject_invalid(self, request):
        if request.method == "OPTIONS" or not self._is_protected_path(request):
            return False
        if settings.API_CLIENT_AUTH_REQUIRED:
            return True
        if requires_signed_read(request.path_info):
            return True
        # Authentication remains optional during rollout, but credentials that opt in
        # to the nonce protocol must fail closed. Otherwise a replay would merely fall
        # through as anonymous while API_CLIENT_AUTH_REQUIRED is disabled.
        if request.headers.get("X-Nonce"):
            return True
        return settings.APICLIENT_REQUIRE_NONCE and self._has_hmac_credentials(request)

    def _has_hmac_credentials(self, request):
        return bool(
            request.headers.get("X-Timestamp")
            or request.headers.get("X-Signature")
            or request.headers.get("X-Nonce")
        )

    def _is_protected_path(self, request):
        # A subscribable calendar client cannot produce SpaceWorks HMAC headers. The
        # 256-bit, independently rate-limited feed token is the authentication for this
        # one route, so applying the frontend-client gate would make every subscription
        # fail when API_CLIENT_AUTH_REQUIRED is enabled.
        from apps.makerspaces.calendar_bearers import is_calendar_feed_bearer_path

        if is_calendar_feed_bearer_path(request.path_info):
            return False
        return requires_signed_read(request.path_info) or any(
            request.path.startswith(p) for p in settings.HMAC_PROTECTED_PATH_PREFIXES
        )

    def _is_valid(self, request):
        request._api_client_signed_target_hidden = False
        set_failure_reason(request, NO_CREDENTIALS)
        # X-Nonce selects the signed protocol. It must never be accepted through the
        # publishable-key or browser-client paths, where it would be replay decoration
        # rather than authenticated input.
        if not self._has_hmac_credentials(request) and not requires_signed_read(request.path_info):
            if self._publishable_key_is_valid(request):
                return True
            if self._frontend_client_is_valid(request):
                return True
        try:
            from apps.apiclients.models import ApiClient

            client_id = request.headers.get("X-Client-Id", "")
            timestamp = request.headers.get("X-Timestamp", "")
            signature = request.headers.get("X-Signature", "")
            nonce = request.headers.get("X-Nonce", "")
            if not (client_id and timestamp and signature):
                return False
            client = ApiClient.objects.filter(
                client_id=client_id, is_active=True
            ).first()
            if client is None:
                set_failure_reason(request, UNKNOWN_CLIENT)
                return False
            if not self._origin_ok(request, client):
                set_failure_reason(request, ORIGIN_DENIED)
                return False
            try:
                skew = abs(int(time.time()) - int(timestamp))
            except ValueError:
                set_failure_reason(request, SKEW)
                return False
            if skew > settings.HMAC_MAX_CLOCK_SKEW_SECONDS:
                set_failure_reason(request, SKEW)
                return False

            if nonce:
                if not nonce_is_valid(nonce):
                    set_failure_reason(request, BAD_SIGNATURE)
                    return False
            elif settings.APICLIENT_REQUIRE_NONCE:
                set_failure_reason(request, NONCE_MISSING)
                return False
            elif body_could_re_encode_nonce(request.body):
                logger.warning(
                    AMBIGUOUS_NONCE_BODY_EVENT, extra={"client_id": client_id}
                )
                set_failure_reason(request, BAD_SIGNATURE)
                return False

            message_parts = [
                request.method.upper().encode(),
                request.get_full_path().encode(),
                timestamp.encode(),
            ]
            if nonce:
                message_parts.append(nonce.encode())
            message_parts.append(request.body)
            message = b"\n".join(message_parts)
            current_secret = client.get_secret()
            previous_secret_is_active = bool(
                client.previous_secret_encrypted and client.previous_secret_valid_until
                and client.previous_secret_valid_until > timezone.now()
            )
            previous_token = (
                client.previous_secret_encrypted if previous_secret_is_active
                else client.secret_encrypted
            )
            previous_secret = decrypt_secret(previous_token)
            current_expected = hmac.new(
                current_secret.encode(), message, hashlib.sha256
            ).hexdigest()
            previous_expected = hmac.new(
                previous_secret.encode(), message, hashlib.sha256
            ).hexdigest()
            current_matches = hmac.compare_digest(signature, current_expected)
            previous_matches = hmac.compare_digest(signature, previous_expected)
            if not (current_matches | previous_matches):
                set_failure_reason(request, BAD_SIGNATURE)
                return False
            if nonce:
                try:
                    claimed = claim_nonce(client_id, nonce)
                except SharedCacheUnavailable:
                    set_failure_reason(request, NONCE_STORE_UNAVAILABLE)
                    return False
                if not claimed:
                    set_failure_reason(request, NONCE_REPLAY)
                    return False
            else:
                logger.warning(
                    LEGACY_NONCE_WARNING_EVENT,
                    extra={"client_id": client_id},
                )
            # Only an authenticated, replay-checked caller may learn a target refusal.
            if not self._scope_checks_ok(request, client):
                request._api_client_signed_target_hidden = self._signed_target_hidden(request, client)
                return False
            request.api_client = client
            request.api_client_signature_verified = True
            telemetry.record_signed_client_observation(request, client)
            return True
        except Exception:  # fail safe - never 500 the request flow
            set_failure_reason(request, BAD_SIGNATURE)
            logger.exception("ApiClient signature validation failed")
            return False

    def _origin_ok(self, request, client):
        raw = request.headers.get("Origin") or request.headers.get("Referer", "")
        if not raw:
            # Server-to-server shapes send no Origin; a peer is another space's backend.
            return client.client_type in ("server", "peer")
        if not client.allowed_origins:
            return False
        parts = urlsplit(raw)
        candidate = f"{parts.scheme}://{parts.netloc}" if parts.scheme else ""
        return candidate in set(client.allowed_origins)

    def _frontend_client_is_valid(self, request):
        try:
            from apps.apiclients.models import ApiClient

            client_id = request.headers.get("X-Client-Id", "")
            timestamp = request.headers.get("X-Timestamp", "")
            signature = request.headers.get("X-Signature", "")
            if not client_id or timestamp or signature:
                return False
            client = ApiClient.objects.select_related("makerspace").filter(
                client_id=client_id,
                is_active=True,
            ).first()
            if client is None:
                set_failure_reason(request, UNKNOWN_CLIENT)
                return False
            # Browser identity is public config, so this path never grants a rate tier.
            if client.client_type != "browser" or not self._origin_ok(request, client):
                set_failure_reason(request, ORIGIN_DENIED)
                return False
            valid = self._scope_checks_ok(request, client)
            if valid:
                telemetry.record_browser_client_observation(request, client)
            return valid
        except Exception:
            logger.exception("Frontend ApiClient validation failed")
            return False
