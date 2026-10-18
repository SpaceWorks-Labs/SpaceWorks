"""Authentication counts with only explicitly recorded tenant attribution."""

from django.db.models import Case, CharField, Q, Value, When

from apps.audit.models import AuditLog
from apps.makerspaces.platform import module_enabled
from .report_fields_hi import MOBILE_AUTH_FIELDS, MOBILE_AUTH_GROUPS
from .reports_common import report_spaces
from .reports_hi_common import buckets, category, combine_counts, result

# Reasons are server-owned codes, not a projection of arbitrary audit metadata.
# Public labels also avoid credential-like strings in decoded report artifacts.
REASONS = {
    "invalid_request": "invalid_request", "invalid_challenge": "invalid_challenge",
    "provider_unavailable": "provider_unavailable", "attestation_rejected": "attestation_rejected",
    "password_login_disabled": "login_disabled", "invalid_credentials": "authentication_rejected",
    "registration_not_approved": "registration_not_approved",
    "device_superadmin_not_supported": "authority_not_supported",
}
LOGIN_ACTIONS = ("auth.device_login_succeeded", "auth.device_login_failed")
ATTESTATION_ACTIONS = ("auth.device_attestation_succeeded", "auth.device_attestation_failed")


def build_mobile_auth(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "mobile"):
        if not module_enabled(space, "mobile"):
            continue
        space_records = []
        # Do not follow actor memberships or registration IDs to guess a tenant.
        # Legacy NULL-scoped rows without recorded selection remain platform facts.
        qs = AuditLog.objects.filter(
            Q(makerspace=space) | Q(makerspace__isnull=True, meta__makerspace_id=space.pk),
            action__in=(*LOGIN_ACTIONS, *ATTESTATION_ACTIONS),
        ).annotate(
            app_platform=category("meta__platform", ("apple", "android")),
            app_environment=category("meta__environment", ("development", "production")),
            failure_reason=Case(*[When(meta__reason=key, then=Value(label)) for key, label in REASONS.items()],
                                default=Value("unknown"), output_field=CharField()),
        )
        dims = ("action", "app_platform", "app_environment", "failure_reason")
        for row in buckets(qs, "created_at", space, grain, date_range, dims):
            action = row["action"]
            succeeded = action.endswith("_succeeded")
            metrics = ["device_logins" if action in LOGIN_ACTIONS else "attestation"]
            if action == "auth.device_login_failed" and row["failure_reason"] in (
                "provider_unavailable", "attestation_rejected", "invalid_challenge",
            ):
                metrics.append("attestation")
            for metric in metrics:
                record = dict(period=row["period"].date().isoformat(), metric=metric,
                              platform=row["app_platform"], environment=row["app_environment"],
                              outcome="succeeded" if succeeded else "failed",
                              reason="none" if succeeded else row["failure_reason"], count=row["count"])
                space_records.append(record)
        # Several audit actions may contribute to one public outcome bucket.
        for row in combine_counts([(space.pk, space_records)], limit=None,
                                  groups=MOBILE_AUTH_GROUPS, counts=("count",)):
            if makerspace_id is None:
                row["makerspace_id"] = space.pk
            records.append(row)
    return result(MOBILE_AUTH_FIELDS, records, makerspace_id is None, limit,
                  basis="Tenant outcomes require an audit tenant or recorded tenant selection; attestation reasons are a subset of login failures and are not additive with logins.",
                  limitations="The identifier-free attestation ledger has no tenant attribution and is reserved for platform analytics. Legacy audit dimensions are unknown.")
