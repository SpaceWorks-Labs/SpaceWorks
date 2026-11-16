"""Analytics connection services: describe, update, create/rotate/revoke the login, embed.

Every create, rotate, revoke and view of the credentials, every connection change and every
dashboard opened is audited with literal actions. Audit metadata names fields, the role and
the dashboard number; it never carries a URL, a secret or a password. The password is
returned once, by create and rotate, and is only ever stored as ciphertext.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record

from . import embedding, provisioning
from .catalogue.registry import VIEWS_VERSION
from .grafana_validation import uses_metabase
from .models import AnalyticsConnection, PlatformAnalyticsConnection, validate_dashboards


class AnalyticsError(Exception):
    status = 409

    def __init__(self, code, detail):
        super().__init__(detail)
        self.code, self.detail = code, detail


def _row(scope, *, lock=False):
    if scope.platform:
        PlatformAnalyticsConnection.load()
        queryset = PlatformAnalyticsConnection.objects.filter(singleton=True)
    else:
        AnalyticsConnection.objects.get_or_create(makerspace=scope.makerspace)
        queryset = AnalyticsConnection.objects.filter(makerspace=scope.makerspace)
    return (queryset.select_for_update() if lock else queryset).get()


def summary(scope, row=None):
    row = row or _row(scope)
    available, reason = provisioning.availability()
    return {
        "available": available, "reason": reason, "views_version": VIEWS_VERSION, "provider": row.provider,
        "configured": bool(uses_metabase(row.provider) and row.metabase_url and row.embed_secret),
        "dashboards": list(row.dashboards or []),
    }


def describe(scope, actor):
    """The manager view of the connection (never a secret). Audited as a credentials view."""
    row = _row(scope)
    login_exists = provisioning.login_exists(row.login_role)
    record(actor, "analytics.credentials_viewed", makerspace=scope.makerspace, target=row,
           meta={"scope": scope.label, "role": row.login_role or ""})
    return {
        **summary(scope, row),
        "metabase_url": row.metabase_url,
        "embed_secret_set": bool(row.embed_secret),
        "show_member_details": None if scope.platform else row.show_member_details,
        "login": {"role": row.login_role, "exists": login_exists,
                  "created_at": row.login_created_at, "rotated_at": row.login_rotated_at},
        "database": provisioning.connection_details(platform=scope.platform),
    }


def update(scope, actor, data):
    from contextlib import nullcontext

    from apps.tenant_migration.gate_runtime import tenant_write

    changed = []
    # A space's connection is tenant data: it participates in the tenant gate like telemetry does.
    gate = nullcontext() if scope.platform else tenant_write(scope.makerspace.pk)
    with gate, transaction.atomic():
        row = _row(scope, lock=True)
        if "metabase_url" in data:
            try:
                url = embedding.normalize_site_url(data["metabase_url"])
            except embedding.EmbedUrlInvalid as exc:
                raise ValidationError({"metabase_url": [str(exc)]}) from None
            if url != row.metabase_url:
                if url and not row.metabase_url and not scope.platform:  # a NEW connection (decision 284)
                    from apps.managed_hosting.extra_quotas import check_extra_quota
                    check_extra_quota(scope.makerspace, "analytics_connections")
                row.metabase_url, changed = url, [*changed, "metabase_url"]
        if "embed_secret" in data:
            secret = (data["embed_secret"] or "").strip()
            if secret and len(secret) < 32:
                raise ValidationError({"embed_secret": [gettext("The Metabase embedding secret is at least 32 characters.")]})
            row.set_embed_secret(secret) if secret else setattr(row, "embed_secret", "")
            changed.append("embed_secret")
        if "dashboards" in data:
            dashboards = [{"id": entry["id"], "title": entry["title"].strip()} for entry in data["dashboards"]]
            validate_dashboards(dashboards)
            if dashboards != row.dashboards:
                row.dashboards, changed = dashboards, [*changed, "dashboards"]
        if "provider" in data and data["provider"] != row.provider:
            row.provider, changed = data["provider"], [*changed, "provider"]
        if "show_member_details" in data and not scope.platform:
            if bool(data["show_member_details"]) != row.show_member_details:
                row.show_member_details, changed = bool(data["show_member_details"]), [*changed, "show_member_details"]
        if changed:
            row.save()
            record(actor, "analytics.connection_updated", makerspace=scope.makerspace, target=row, meta={
                "scope": scope.label, "fields": sorted(changed),
                "show_member_details": row.show_member_details if "show_member_details" in changed else None,
            })
    return describe(scope, actor)


def _require_available():
    available, reason = provisioning.availability()
    if not available:
        raise AnalyticsError("analytics_not_available",
                             "Analytics logins are not available on this hosting: the database owner cannot create "
                             "roles." if reason == "not_available_on_hosting" else
                             "Analytics logins are not available on this deployment.")


def _credentials(scope, row, password):
    return {"role": row.login_role, "password": password,
            **provisioning.connection_details(platform=scope.platform)}


def _set_login(scope, actor, *, rotate):
    _require_available()
    makerspace_id = None if scope.platform else scope.makerspace.pk
    with transaction.atomic():
        row = _row(scope, lock=True)
        if rotate and not row.login_role:
            raise AnalyticsError("analytics_login_missing", "There is no login to rotate; create one first.")
        if not rotate and row.login_role:
            raise AnalyticsError("analytics_login_exists", "A login already exists; rotate or revoke it.")
        role = row.login_role or provisioning.generate_login_name(makerspace_id)
        password = provisioning.new_password()
        try:
            provisioning.ensure_login(role, password, makerspace_id)
        except provisioning.ProvisioningFailed:
            raise AnalyticsError("analytics_login_failed",
                                 "Could not create the database login. Nothing was changed.") from None
        now = timezone.now()
        row.login_role = role
        row.set_login_password(password)
        if rotate:
            row.login_rotated_at = now
        else:
            row.login_created_at, row.login_rotated_at = now, None
        row.save()
        # One literal action per branch keeps both under the audit presentation catalogue.
        if rotate:
            record(actor, "analytics.login_rotated", makerspace=scope.makerspace, target=row,
                   meta={"scope": scope.label, "role": role, "password_shown": True})
        else:
            record(actor, "analytics.login_created", makerspace=scope.makerspace, target=row,
                   meta={"scope": scope.label, "role": role, "password_shown": True})
    return _credentials(scope, row, password)


def create_login(scope, actor):
    return _set_login(scope, actor, rotate=False)


def rotate_login(scope, actor):
    return _set_login(scope, actor, rotate=True)


def revoke_login(scope, actor):
    with transaction.atomic():
        row = _row(scope, lock=True)
        if not row.login_role:
            raise AnalyticsError("analytics_login_missing", "There is no login to revoke.")
        role = row.login_role
        available, _reason = provisioning.availability()
        if available:
            # Also clears a FixedRoleScope row a restore left behind without its role.
            try:
                provisioning.drop_login(role)
            except provisioning.ProvisioningFailed:
                raise AnalyticsError("analytics_login_failed",
                                     "Could not remove the database login. Nothing was changed.") from None
        elif provisioning.login_exists(role):
            _require_available()
        row.login_role, row.login_password = "", ""
        row.login_created_at = row.login_rotated_at = None
        row.save()
        record(actor, "analytics.login_revoked", makerspace=scope.makerspace, target=row,
               meta={"scope": scope.label, "role": role})


def embed(scope, actor, dashboard_id):
    row = _row(scope)
    if not (uses_metabase(row.provider) and row.metabase_url and row.embed_secret):
        raise AnalyticsError("analytics_not_configured", "Metabase is not connected yet.")
    if dashboard_id not in {entry["id"] for entry in row.dashboards or []}:
        raise AnalyticsError("analytics_dashboard_unknown", "That dashboard is not listed for this space.")
    url, expires_at = embedding.dashboard_url(row.metabase_url, row.get_embed_secret(), dashboard_id)
    record(actor, "analytics.dashboard_viewed", makerspace=scope.makerspace, target=row,
           meta={"scope": scope.label, "dashboard": dashboard_id})
    return {"url": url, "expires_at": expires_at}
