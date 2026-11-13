"""Decision 263: the Grafana half of an analytics connection (space or platform).

Every view, change, token set/rotate/revoke, connection test, bundle download and dashboard
opened is audited with a literal action whose metadata names fields, the provider, the
dashboard uid and the outcome: never a URL, a token, an access token or a password. The
token is stored as ciphertext and is only decrypted to call this scope's own Grafana.
"""

from contextlib import nullcontext

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit.services import record

from . import grafana_bundle, grafana_client, provisioning
from .catalogue.registry import VIEWS_VERSION
from .grafana_validation import normalize_grafana_url, uses_grafana, validate_grafana_dashboards
from .services import AnalyticsError, _row


def _gate(scope):
    from apps.tenant_migration.gate_runtime import tenant_write

    return nullcontext() if scope.platform else tenant_write(scope.makerspace.pk)


def _listed(row):
    return [{"uid": entry["uid"], "title": entry["title"], "mode": entry["mode"]} for entry in row.grafana_dashboards or []]


def summary(scope, row=None):
    row = row or _row(scope)
    on = uses_grafana(row.provider)
    return {"provider": row.provider, "views_version": VIEWS_VERSION,
            "configured": bool(on and row.grafana_url and row.grafana_dashboards),
            "dashboards": _listed(row) if on else []}


def _connection(scope, row):
    return {
        "provider": row.provider, "grafana_url": row.grafana_url, "org_id": row.grafana_org_id,
        "token_set": bool(row.grafana_token), "token_updated_at": row.grafana_token_set_at,
        "dashboards": list(row.grafana_dashboards or []), "login_role": row.login_role,
        "database": provisioning.connection_details(platform=scope.platform),
        "private_hosts_allowed": grafana_client.private_hosts_allowed(scope),
    }


def describe(scope, actor):
    row = _row(scope)
    record(actor, "analytics.grafana_credentials_viewed", makerspace=scope.makerspace, target=row,
           meta={"scope": scope.label, "token_set": bool(row.grafana_token)})
    return _connection(scope, row)


def update(scope, actor, data):
    changed = []
    with _gate(scope), transaction.atomic():
        row = _row(scope, lock=True)
        if "provider" in data and data["provider"] != row.provider:
            row.provider, changed = data["provider"], [*changed, "provider"]
        if "grafana_url" in data:
            try:
                url = normalize_grafana_url(data["grafana_url"])
            except ModelValidationError as exc:
                raise ValidationError({"grafana_url": exc.messages}) from None
            if url != row.grafana_url:
                if url and not row.grafana_url and not scope.platform:  # a NEW connection (decision 284)
                    from apps.managed_hosting.extra_quotas import check_extra_quota
                    check_extra_quota(scope.makerspace, "analytics_connections")
                row.grafana_url, changed = url, [*changed, "grafana_url"]
        if "org_id" in data and data["org_id"] != row.grafana_org_id:
            row.grafana_org_id, changed = data["org_id"], [*changed, "org_id"]
        if "dashboards" in data:
            boards = [{"uid": entry["uid"], "title": entry["title"].strip(), "mode": entry["mode"],
                       "public_token": entry.get("public_token") or ""} for entry in data["dashboards"]]
            try:
                validate_grafana_dashboards(boards)
            except ModelValidationError as exc:
                raise ValidationError({"dashboards": exc.messages}) from None
            if boards != row.grafana_dashboards:
                row.grafana_dashboards, changed = boards, [*changed, "dashboards"]
        if changed:
            row.save()
            record(actor, "analytics.grafana_connection_updated", makerspace=scope.makerspace, target=row,
                   meta={"scope": scope.label, "fields": sorted(changed), "provider": row.provider})
    return describe(scope, actor)


def set_token(scope, actor, token):
    token = (token or "").strip()
    if not 8 <= len(token) <= 512 or any(ch.isspace() for ch in token):
        raise ValidationError({"token": [gettext("A Grafana token is 8 to 512 characters with no spaces.")]})
    with _gate(scope), transaction.atomic():
        row = _row(scope, lock=True)
        rotated = bool(row.grafana_token)
        row.set_grafana_token(token)
        row.grafana_token_set_at = timezone.now()
        row.save()
        # One literal action per branch keeps both under the audit presentation catalogue.
        if rotated:
            record(actor, "analytics.grafana_token_rotated", makerspace=scope.makerspace, target=row,
                   meta={"scope": scope.label})
        else:
            record(actor, "analytics.grafana_token_created", makerspace=scope.makerspace, target=row,
                   meta={"scope": scope.label})
    return describe(scope, actor)


def revoke_token(scope, actor):
    with _gate(scope), transaction.atomic():
        row = _row(scope, lock=True)
        if not row.grafana_token:
            raise AnalyticsError("grafana_token_missing", gettext("There is no Grafana token to revoke."))
        row.grafana_token, row.grafana_token_set_at = "", None
        row.save()
        record(actor, "analytics.grafana_token_revoked", makerspace=scope.makerspace, target=row,
               meta={"scope": scope.label})


def bundle(scope, actor, *, archive=False):
    row = _row(scope)
    body = grafana_bundle.build(scope, row)
    record(actor, "analytics.grafana_bundle_downloaded", makerspace=scope.makerspace, target=row,
           meta={"scope": scope.label, "areas": body["areas"], "archive": bool(archive)})
    return grafana_bundle.to_zip(body) if archive else body


def configured_row(scope):
    row = _row(scope)
    if not uses_grafana(row.provider):
        raise AnalyticsError("grafana_not_enabled", gettext("Grafana is not switched on for analytics here."))
    if not row.grafana_url:
        raise AnalyticsError("grafana_not_configured", gettext("Grafana is not connected yet."))
    return row


def listed(row, uid):
    for entry in row.grafana_dashboards or []:
        if entry["uid"] == uid:
            return entry
    raise AnalyticsError("grafana_dashboard_unknown", gettext("That Grafana dashboard is not listed here."))
