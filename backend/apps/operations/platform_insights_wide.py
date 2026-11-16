"""Wider superadmin insights (parity E-B8, A16): activity, security posture and storage, as platform-level COUNTS.

No names, addresses, message subjects or bodies, tokens, secrets or free text are read here; every value is a count,
a size or a label from a closed set. Event-derived numbers return `None` when the Events module is off.
"""

from django.db.models import Count, Q, Sum

SENSITIVE_ACTIONS = (
    "auth.mfa_reset", "auth.ip_auto_blocked", "auth.passkey_removed", "auth.social_identity_unlinked",
    "api_client.created", "api_client.revoked", "api_client.secret_rotated", "api_client.scopes_changed",
    "account.credentials_revoked", "account.purged",
)
CLIENT_STATES = ("active", "revoked")


def _activity(spaces, start, now):
    from apps.separability.registry import runtime_active
    if not runtime_active("events"):
        return None
    from apps.events.models import Event, EventRegistration
    from apps.events.models_attendance import EventCheckInEvent
    from apps.events.models_broadcasts import EventBroadcast
    from apps.events.models_feedback import EventFeedbackResponse
    def span(field):
        return {f"{field}__gte": start, f"{field}__lt": now}
    broadcasts = EventBroadcast.objects.filter(makerspace__in=spaces, status="sent", **span("completed_at"))
    return {
        "events_held": Event.objects.filter(makerspace__in=spaces, **span("starts_at")).count(),
        "registrations": EventRegistration.objects.filter(event__makerspace__in=spaces, **span("created_at")).count(),
        "check_ins": EventCheckInEvent.objects.filter(registration__event__makerspace__in=spaces,
                                                     **span("recorded_at")).count(),
        "feedback_responses": EventFeedbackResponse.objects.filter(survey__event__makerspace__in=spaces,
                                                                   **span("created_at")).count(),
        "broadcasts_sent": broadcasts.count(),
        "recent_broadcasts": [
            {"completed_at": row["completed_at"], "audience_statuses": row["statuses"],
             "audience_attendance": row["attendance"]}
            for row in broadcasts.order_by("-completed_at").values("completed_at", "statuses", "attendance")[:5]],
    }


def _posture(accounts, start, now):
    from apps.accounts.models_social import SocialIdentity
    from apps.accounts.models_webauthn import WebAuthnCredential
    from apps.apiclients.models import ApiClient
    from apps.audit.models import AuditLog
    live = accounts.filter(is_active=True)
    social = (SocialIdentity.objects.filter(user__in=live).values("provider").annotate(n=Count("user", distinct=True)))
    # Collapse open-ended `oidc:<slug>` providers into one label so a provider name is never a row key.
    mix = {}
    for row in social:
        key = "oidc" if row["provider"].startswith("oidc:") else row["provider"]
        mix[key] = mix.get(key, 0) + row["n"]
    actions = {row["action"]: row["n"] for row in AuditLog.objects.filter(
        action__in=SENSITIVE_ACTIONS, created_at__gte=start, created_at__lt=now).values("action").annotate(n=Count("pk"))}
    clients = ApiClient.objects.aggregate(active=Count("pk", filter=Q(is_active=True)),
                                          revoked=Count("pk", filter=Q(is_active=False)),
                                          rotating=Count("pk", filter=Q(is_active=True, previous_secret_valid_until__gt=now)),
                                          unused_in_window=Count("pk", filter=Q(is_active=True) & (
                                              Q(last_seen_at__isnull=True) | Q(last_seen_at__lt=start))))
    return {
        "accounts_unverified": live.filter(email_verified_at__isnull=True).count(),
        "accounts_with_passkey": live.filter(pk__in=WebAuthnCredential.objects.values("user_id")).count(),
        "login_methods": [{"method": key, "accounts": mix[key]} for key in sorted(mix)],
        "sensitive_actions": [{"action": name, "count": actions.get(name, 0)} for name in SENSITIVE_ACTIONS],
        "api_clients": clients,
    }


def _storage(spaces):
    total = spaces.aggregate(bytes=Sum("storage_bytes_used"), spaces=Count("pk"))
    return {"total_bytes": total["bytes"] or 0, "spaces": total["spaces"],
            "largest_bytes": list(spaces.order_by("-storage_bytes_used").values_list("storage_bytes_used", flat=True)[:5])}


def wide_insights(spaces, accounts, start, now):
    return {"activity": _activity(spaces, start, now), "security": _posture(accounts, start, now),
            "storage": _storage(spaces)}
