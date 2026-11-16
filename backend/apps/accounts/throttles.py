from collections.abc import Mapping

from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class PasswordResetEmailThrottle(SimpleRateThrottle):
    scope = "password_reset_email"

    def get_cache_key(self, request, view):
        from apps.accounts.audit_events import fingerprint

        raw = request.data.get("email") if isinstance(request.data, Mapping) else None
        email = (str(raw).strip().lower()
                 if isinstance(raw, (str, int, float)) and not isinstance(raw, bool) else "")
        if not email:
            return None
        context = request.data.get("context", "member")
        if isinstance(context, str) and context in {"staff", "platform"}:
            from apps.accounts.password_reset_context import resolve_account
            slug = request.data.get("makerspace")
            if slug is not None and not isinstance(slug, str):
                return None
            account = resolve_account(str(raw).strip(), context=context, makerspace=slug)
            email = f"{context}:{slug or ''}:{account.pk if account else email}"
        return self.cache_format % {
            "scope": self.scope,
            "ident": fingerprint(email),
        }


class PasswordResetConfirmEmailThrottle(PasswordResetEmailThrottle):
    """Per-address guessing budget, separate from the resend allowance."""

    scope = "password_reset_confirm_email"


class MemberVerificationEmailThrottle(SimpleRateThrottle):
    scope = "member_verification_email"

    def get_cache_key(self, request, view):
        from apps.accounts.audit_events import fingerprint

        raw = request.data.get("email") if isinstance(request.data, Mapping) else None
        email = raw if isinstance(raw, str) and raw.strip() else getattr(request.user, "email", "")
        email = str(email or "").strip().lower()
        if not email:
            return None
        # A fingerprint, never the address: cache keys are visible to anyone with Redis access (decision 339).
        return self.cache_format % {"scope": self.scope, "ident": fingerprint(email)}


MemberSignUpEmailThrottle = MemberVerificationEmailThrottle


class PhoneOtpNumberThrottle(SimpleRateThrottle):
    """Per-number cap, so one handset cannot be texted repeatedly from many IPs.

    Keyed on a fingerprint of the submitted number, never the number itself: throttle
    keys land in the cache and a raw phone number there is PII at rest.
    """

    scope = "phone_otp_number"

    def get_cache_key(self, request, view):
        from apps.accounts.audit_events import fingerprint
        from apps.accounts.phone_numbers import normalize_or_none

        phone = normalize_or_none(request.data.get("phone"))
        return None if not phone else self.cache_format % {
            "scope": self.scope, "ident": fingerprint(phone)
        }


class PhoneConfirmNumberThrottle(PhoneOtpNumberThrottle):
    """Per-number cap on code GUESSES, budgeted separately from code REQUESTS.

    Sharing one bucket with PhoneOtpNumberThrottle looked tidier and was wrong: a
    member who mistypes a code three times would spend the same allowance used to send
    it and be locked out for an hour with a valid code in hand. Guessing and requesting
    are different actions with different abuse profiles, so they get different budgets.
    The per-challenge attempt counter is still the tighter of the two limits.
    """

    scope = "phone_confirm_number"


class PhoneOtpRequestThrottle(SimpleRateThrottle):
    """Per-IP cap on code requests -- the number-enumeration sweep defence."""

    scope = "phone_otp_request"

    def get_cache_key(self, request, view):
        return self.get_ident(request) and self.cache_format % {
            "scope": self.scope, "ident": self.get_ident(request)
        }


class PhoneLoginConfirmThrottle(SimpleRateThrottle):
    """Per-IP cap on code guesses.

    The per-challenge attempt counter caps guesses against ONE challenge; this caps an
    attacker who keeps requesting fresh challenges to reset that counter.
    """

    scope = "phone_login_confirm"

    def get_cache_key(self, request, view):
        return self.get_ident(request) and self.cache_format % {
            "scope": self.scope, "ident": self.get_ident(request)
        }


class DeviceLoginThrottle(SimpleRateThrottle):
    scope = "device_login"

    def get_cache_key(self, request, view):
        return self.get_ident(request) and self.cache_format % {
            "scope": self.scope, "ident": self.get_ident(request)
        }


class DeviceLoginUserThrottle(SimpleRateThrottle):
    scope = "device_login_user"

    def get_cache_key(self, request, view):
        from apps.accounts.audit_events import fingerprint

        username = str(request.data.get("username") or "").strip().lower()
        return None if not username else self.cache_format % {
            "scope": self.scope, "ident": fingerprint(username)
        }


class NativeSocialLinkThrottle(ScopedRateThrottle):
    """The view's ``social_link`` budget, spent only by native (device-grant) linking.

    Returning no cache key exempts browser linking and every non-POST request, exactly
    as the former view-level ``get_throttles()`` selection did.
    """

    def get_cache_key(self, request, view):
        if request.method != "POST" or getattr(request, "device_grant", None) is None:
            return None
        return super().get_cache_key(request, view)
