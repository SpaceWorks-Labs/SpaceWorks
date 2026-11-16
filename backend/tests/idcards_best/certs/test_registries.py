"""Certificate routes and models join every registry a new route or model must join."""
from django.urls import reverse

MODELS = ("events.EventCertificateSignatory", "events.EventCertificateSignatoryApproval")


def _routes():
    from apps.accounts.programme_route_catalog_certificates import CERTIFICATE_ROUTES
    return [name for name, methods, target in CERTIFICATE_ROUTES]


def test_every_route_is_catalogued_native_and_mounted():
    from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_DECISIONS
    from django.urls import get_resolver
    names = {name for name in get_resolver().reverse_dict.keys() if isinstance(name, str)}
    for name in _routes():
        assert name in BY_NAME and NATIVE_DECISIONS[name] == "native"
        assert name in names, name
    assert reverse("events-programme-admin-certificate-signatories", kwargs={"pk": 1}).endswith(
        "/admin/events/1/certificates/signatories/")


def test_admin_routes_are_staff_surface_and_session_only():
    from apps.accounts.delegated_routes import route_class
    from apps.apiclients.scope_registry_programme import SESSION_ONLY
    for name in _routes():
        if "-admin-" in name:
            assert route_class(name) is not None and name in SESSION_ONLY, name


def test_models_are_in_the_tenant_dump_and_export_catalogues():
    from apps.data_export.classification import EXPORTED_MODEL_FIELDS
    from apps.data_export.datasets import PROGRAMME_DATASETS
    from apps.tenant_migration.catalog_events_programme import FIELD_NAMES
    for label in MODELS:
        assert label in FIELD_NAMES and label in EXPORTED_MODEL_FIELDS and label in PROGRAMME_DATASETS
    assert "signatory_approval_required" in EXPORTED_MODEL_FIELDS["events.EventCertificatePublicationPolicy"]
    assert "certificate_kind" in EXPORTED_MODEL_FIELDS["events.EventCertificateTemplateRevision"]


def test_ownership_predicates_reach_the_makerspace():
    from apps.tenant_rls.policies import build_plans
    plans, unresolved = build_plans()
    assert not {label for label in unresolved if "Signatory" in label}


def test_user_edges_are_classified():
    from apps.accounts.merge_registry import disposition_for
    assert disposition_for("events.EventCertificateSignatory", "member") is not None
    assert disposition_for("events.EventCertificateSignatoryApproval", "approved_by") is not None


def test_audit_actions_are_presented():
    from apps.audit.presentation_catalog import PRESENTATION_CATALOG
    from apps.audit.presentation_catalog_r2_certificates import ENTRIES
    assert {entry.action for entry in ENTRIES} <= set(PRESENTATION_CATALOG)


def test_purge_order_puts_signatory_rows_first():
    from apps.makerspaces.purge_events_programme_catalog import PURGE_ORDER
    labels = [label for label, _path in PURGE_ORDER]
    assert labels.index("events.EventCertificateSignatoryApproval") < labels.index("events.EventCertificateSignatory")


def test_signature_notice_is_in_the_catalogue():
    from apps.integrations.notification_catalog_events_programme import PROGRAMME_EVENTS
    assert "certificate_signature_requested" in PROGRAMME_EVENTS
