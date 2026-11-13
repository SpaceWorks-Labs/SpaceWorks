"""Fail-closed model, table and field guards for the Lane D source catalog."""

from collections import Counter
import hashlib
import json

from django.apps import apps

from .tenant_dump_authority import AUTHORITY_FIELD_OVERRIDES
from .tenant_dump_field_snapshot import (
    AUTO_CREATED_FIELD_NAMES,
    FIRST_PARTY_FIELD_NAMES,
    THIRD_PARTY_FIELD_NAMES,
    UNMANAGED_FIELD_NAMES,
)
from .tenant_dump_model_catalog import (
    AUTO_CREATED_TABLE_RULES,
    FIRST_PARTY_APP_LABELS,
    FIRST_PARTY_MODEL_RULES,
    THIRD_PARTY_INSTALLED_APP_LABELS,
    THIRD_PARTY_MODEL_APP_LABELS,
    THIRD_PARTY_MODEL_RULES,
    UNMANAGED_MODEL_RULES,
    UNOWNED_TABLE_RULES,
)
from .tenant_dump_types import (
    AuthorityDisposition,
    AuthorityField,
    ModelDisposition,
    NoAuthorityField,
    authority,
)


class TenantDumpCatalogError(AssertionError):
    pass


# SHA-256 of the ordered model/table/field graph produced by catalog_schema.
# Updating it is an explicit review act; runtime introspection never blesses drift.
# Bootstrap union: T account kinds, governance, documents, profiles and presence;
# O native grants, account lifecycle, push, analytics and addressed messaging.
# Literal graph reconstruction reproduced BOTH parent pins before computing this
# merged snapshot digest. Historical repin commentary lives in git history.
# Pages programme: public page/revision/asset models, handles and event session
# identities; re-pinned from schema_digest() over the merged graph.
# Hosting requests (lane/hosting-requests): HostingRequest; re-pinned after that merge.
# Machine-service ETA (lane/machine-eta): cancellation and notice markers; re-pinned.
# Cloud programme (cloud/integration): managed coordination, email providers, cloud
# accounting and storage history; with lane/refunds (refund cases), re-pinned after both merges.
# Events programme (lane/events-final, decision #86): programme, design and fence
# steps plus reimbursements; re-pinned from schema_digest() over the merged graph.
# lane/r1-security: makerspaces/0105 drops anonymous_requests_enabled and accounts/0046 drops
# User.external_checkin_user_id (#80); re-pinned.
# lane/p1b-c: makerspaces/0109 MakerspaceSecurityLock and accounts/0047 PlatformPiiAccessGrant
# (security locks and the superadmin PII window, #114); re-pinned.
# lane/r2-l17: makerspaces/0110 settings authority (grants and SM locks) and 0111 folded
# modules (#97, #101, #128); re-pinned.
# lane/r2-l7b: events/0059-0060 pairwise judging and its guards; re-pinned over L17.
# lane/p1b-b1 (#110/#111): backup/0030-0033 drop archive custody, decision snapshots, Lane E
# restore state and the backup module; tenant_migration/0013 drops dump custody; re-pinned.
# lane/r2-l1b: events/0061 (re-chained after pairwise) public event surface and makerspaces/0112
# closed notice; re-pinned.
# lane/p1b-b2: makerspaces/0113 (re-chained after 0112) drops superadmin_access_enabled;
# backup/0034-0036 per-space backup and restore; accounts/0048; re-pinned.
# lane/r2-l2b: events/0062 (re-chained after L1's 0061) communications, notifications/0011,
# integrations/0049, hosting_requests/0002 and organizations/0008; re-pinned.
# Release-2 batch U-A1 + L4 + L5: accounts/0049-0050 unified accounts, makerspaces/0114 membership
# track and 0115-0117 (L4, re-chained after 0114) membership lifecycle, payments/0031-0032 and
# evidence/0009 finance ledger and receipts; re-pinned.
# lane/r2-s0: accounts/0051-0053 passkeys, login risk and IP access; makerspaces/0118 (re-chained
# after L4's 0117) per-space security policy; re-pinned.
# lane/r2-u-d: tenant_migration/0014 grant_staff_roles on import identity decisions; re-pinned.
# lane/r2-l15c: payments/0033-0034 pricing kernel and guards, bookings/0021 requested price; re-pinned.
# lane/r2-l10-l11: devices/0005 machine integrations, backup/0038 key rotation and drills,
# tenant_migration/0015 self-host move request; re-pinned.
# lane/r2-l12c: inventory/0017, procurement/0009, warranty/0004, hardware_requests/0030,
# machines/0031, maintenance/0004, bookings/0022 machines and loans depth; re-pinned.
# lane/r2-s-a: makerspaces/0119 retires security.staff_mfa_required (catalog unchanged).
# lane/r2-l23: machines/0032 and payments/0035 metered machine sessions; re-pinned.
# lane/r2-l26: makerspaces/0120 (renumbered after S-A's 0119) public stats settings; re-pinned.
# lane/r2-l16: makerspaces/0121-0122 (renumbered) Technician role, maintenance/0005 repairs; re-pinned.
# lane/r2-l3: card_designs/0001-0003, id_programmes/0001, events/0063, makerspaces/0123 (renumbered) ID cards; re-pinned.
# lane/r2-l8: encryption/0012 key rotation, tenant_rls/0001 (both re-chained off makerspaces/0123); re-pinned.
# lane/r2-l6: events/0064-0065 ticketing, payments/0036 (renumbered) event subjects; re-pinned.
# lane/r2-l18: payments/0037, events/0066, makerspaces/0124 (renumbered) donations, sponsors, feeds; re-pinned.
# lane/r2-l21a: events/0067 (renumbered) participation, event_reimbursements/0006; re-pinned.
# lane/r2-l21b: events/0068-0069, payments/0038, accounts/0055 (renumbered) judging money and event grants; re-pinned.
# lane/r2-l22: shop/0001-0002, makerspaces/0125-0126, payments/0040, procurement/0010 (renumbered) shop; re-pinned.
# lane/r2-l25: analytics/0001 (re-chained) connection models; re-pinned.
# lane/r2-gap-ops: maintenance/0006 subject log cost; re-pinned.
# release 2 combined tree (int-stage-r2final): gap-cards makerspaces/0128, events/0071, id_programmes/0002 email format; final re-pin.
# lane/r2-submit-content: events/0072-0074, event_reimbursements/0007 (renumbered) submission stages; re-pinned.
# lane/r2-hack-money: events/0075-0077, payments/0041-0043, event_reimbursements/0008 (renumbered) prize money, deposits, crew pool; re-pinned.
# lane/r2-peoples-choice: events/0078-0079 (renumbered) People's choice config, ballots, results, standings; re-pinned.
# lanes r2-gap-misc, r2-gap-money, r2-superadmin-controls: makerspaces/0129-0131 (chained), space_controls/0001, managed_hosting/0001, hosting_requests/0003; re-pinned.
# lane/r2-gap-api: apiclients/0009-0010 personal tokens, app connections and the peer client type; re-pinned.
# lane/r2-idcards-best: events/0081-0084 certificate thanks, kind designs, signatories and holder name; re-pinned.
# lane/r2-l9: accounts/0057 User.preferred_locale, makerspaces/0132 Makerspace.default_locale (phase 8 i18n); re-pinned.
# Public-stat visibility: makerspaces/0133 adds public_stats_config JSON; class-metadata pin derived read-only.
# Orchestrator verifies this against actual post-migration schema before release.
# 0.12.0 pins (216 events/bookings/maintenance, P2-1 workshop machines, 220(d)2, 221(b), then the
# 221-223 release lanes): each lane's migration additions are folded in; re-pinned at consolidation.
# R2-final: accounts WebSessionActivityDay/ChannelUsageDay models and DeviceGrant login_method "passkey"; re-pinned.
CATALOG_SCHEMA_SHA256 = "79bc0d27f5b4d847745cfb717a76ebe9d82b012ecc8515267aba6e47b73026cf"


def catalog_models(apps_registry=apps):
    """Use Django's complete model universe, including generated M2M tables."""
    return tuple(
        model
        for model in apps_registry.get_models(include_auto_created=True)
        if not model._meta.proxy
    )


def governed_fields(model):
    """Match Django M2Ms even though they are not concrete columns."""
    return tuple(
        field
        for field in model._meta.get_fields()
        if field.concrete or field.many_to_many
    )


def catalog_schema(models=None):
    rows = []
    for model in models or catalog_models():
        rows.append({
            "app_label": model._meta.app_label,
            "auto_created": bool(model._meta.auto_created),
            "db_table": model._meta.db_table,
            "fields": sorted(field.name for field in governed_fields(model)),
            "label": model._meta.label,
            "managed": bool(model._meta.managed),
        })
    return sorted(rows, key=lambda item: item["label"])


def schema_digest(models=None):
    encoded = json.dumps(
        catalog_schema(models), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _default_field_rule(model_rule):
    if model_rule.disposition in {ModelDisposition.DROP, ModelDisposition.EMPTY}:
        return authority(AuthorityDisposition.DROP, model_rule.reason)
    if model_rule.disposition in {ModelDisposition.RESET, ModelDisposition.BOOTSTRAP}:
        return authority(AuthorityDisposition.RESET, model_rule.reason)
    if model_rule.disposition is ModelDisposition.PRESERVE_LIVE:
        return authority(AuthorityDisposition.PRESERVE, model_rule.reason)
    return NoAuthorityField(
        "Ordinary tenant row identity/content; it does not independently select "
        "target authority or disclosure."
    )


def build_field_policies():
    policies = {}
    universes = (
        (FIRST_PARTY_MODEL_RULES, FIRST_PARTY_FIELD_NAMES),
        (AUTO_CREATED_TABLE_RULES, AUTO_CREATED_FIELD_NAMES),
        (THIRD_PARTY_MODEL_RULES, THIRD_PARTY_FIELD_NAMES),
        (UNMANAGED_MODEL_RULES, UNMANAGED_FIELD_NAMES),
    )
    for model_rules, field_names in universes:
        if set(model_rules) != set(field_names):
            raise TenantDumpCatalogError(
                "Lane D model/field snapshot labels drifted; "
                f"missing={sorted(set(model_rules) - set(field_names))}, "
                f"extra={sorted(set(field_names) - set(model_rules))}"
            )
        for label, model_rule in model_rules.items():
            for field_name in field_names[label]:
                policies[(label, field_name)] = _default_field_rule(model_rule)
    for edge, rule in AUTHORITY_FIELD_OVERRIDES.items():
        if edge not in policies:
            raise TenantDumpCatalogError(
                f"Lane D authority override names an ungoverned field: {edge}"
            )
        policies[edge] = rule
    return policies


FIELD_POLICIES = build_field_policies()


def validate_field_coverage(models, declarations):
    actual = {
        (model._meta.label, field.name)
        for model in models
        for field in governed_fields(model)
    }
    declared = set(declarations)
    if declared != actual:
        raise TenantDumpCatalogError(
            "Lane D field catalog drifted; "
            f"missing={sorted(actual - declared)}, extra={sorted(declared - actual)}"
        )
    for edge, rule in declarations.items():
        if not isinstance(rule, (AuthorityField, NoAuthorityField)) or not rule.reason:
            raise TenantDumpCatalogError(f"Lane D field has no disposition/reason: {edge}")
        if isinstance(rule, AuthorityField) and (
            not rule.dispositions
            or any(not isinstance(item, AuthorityDisposition) for item in rule.dispositions)
        ):
            raise TenantDumpCatalogError(f"Lane D authority disposition is invalid: {edge}")


def validate_catalog(
    *,
    apps_registry=apps,
    field_policies=FIELD_POLICIES,
    expected_schema_digest=CATALOG_SCHEMA_SHA256,
    unmanaged_rules=UNMANAGED_MODEL_RULES,
):
    models = catalog_models(apps_registry)
    installed_apps = {config.label for config in apps_registry.get_app_configs()}
    _equal(
        "installed app allowlist",
        set(FIRST_PARTY_APP_LABELS | THIRD_PARTY_INSTALLED_APP_LABELS),
        installed_apps,
    )
    auto = {model._meta.label for model in models if model._meta.auto_created}
    unmanaged = {
        model._meta.label
        for model in models
        if not model._meta.auto_created and not model._meta.managed
    }
    first_party = {
        model._meta.label
        for model in models
        if not model._meta.auto_created
        and model._meta.managed
        and model._meta.app_label in FIRST_PARTY_APP_LABELS
    }
    third_party = {
        model._meta.label
        for model in models
        if not model._meta.auto_created
        and model._meta.managed
        and model._meta.app_label in THIRD_PARTY_MODEL_APP_LABELS
    }
    unknown_managed = {
        model._meta.label
        for model in models
        if not model._meta.auto_created
        and model._meta.managed
        and model._meta.app_label
        not in FIRST_PARTY_APP_LABELS | THIRD_PARTY_MODEL_APP_LABELS
    }
    _equal("first-party model universe", set(FIRST_PARTY_MODEL_RULES), first_party)
    _equal("auto-created through universe", set(AUTO_CREATED_TABLE_RULES), auto)
    _equal("third-party model universe", set(THIRD_PARTY_MODEL_RULES), third_party)
    _equal("unmanaged model universe", set(unmanaged_rules), unmanaged)
    if unknown_managed:
        raise TenantDumpCatalogError(
            f"managed models belong to an unreviewed app allowlist: {sorted(unknown_managed)}"
        )
    if any(rule.disposition is not ModelDisposition.REFUSE for rule in unmanaged_rules.values()):
        raise TenantDumpCatalogError("every unmanaged ORM model must be REFUSE")
    validate_field_coverage(models, field_policies)
    _validate_table_ownership(models)
    actual_digest = schema_digest(models)
    if expected_schema_digest != actual_digest:
        raise TenantDumpCatalogError(
            "Lane D schema/catalog digest drifted; "
            f"expected={expected_schema_digest}, actual={actual_digest}"
        )


def validate_unowned_tables(table_names, *, models=None, rules=UNOWNED_TABLE_RULES):
    owned = {model._meta.db_table for model in models or catalog_models()}
    unowned = set(table_names) - owned
    _equal("unowned database table universe", set(rules), unowned)


def _validate_table_ownership(models):
    counts = Counter(model._meta.db_table for model in models)
    duplicates = sorted(table for table, count in counts.items() if count != 1)
    if duplicates:
        raise TenantDumpCatalogError(
            f"physical tables have multiple model-universe owners: {duplicates}"
        )


def _equal(subject, declared, actual):
    if declared != actual:
        raise TenantDumpCatalogError(
            f"{subject} drifted; missing={sorted(actual - declared)}, "
            f"extra={sorted(declared - actual)}"
        )
