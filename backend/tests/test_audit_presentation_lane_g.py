"""Lane G keeps audit labels exact without widening dynamic metadata disclosure."""

from types import SimpleNamespace

import pytest

from apps.audit.presentation import project
from apps.audit.presentation_catalog import PRESENTATION_CATALOG, WRAPPER_SITE_PREFIXES
from apps.audit.presentation_discovery import DynamicAuditSite, discover_dynamic_audit_sites
from apps.audit.presentation_guards import presentation_catalog_errors
from apps.tenant_migration.audit_reference_guards import discover_audit_meta_references


@pytest.mark.parametrize(("action", "label"), [
    ("event.audience_updated", "Event audience updated"),
    ("event.series_audience_updated", "Event series audience updated"),
    ("event.registration_calendar_downloaded", "Event registration calendar downloaded"),
])
def test_lane_g_actions_have_labels_and_still_redact_dynamic_event_metadata(action, label):
    row = SimpleNamespace(action=action, meta={
        "old_audience": "accounts", "new_audience": "participating_organizations",
        "organization_ids": [3], "email": "private@example.test",
    })
    projection = project(row)
    assert projection.action_label == label
    assert projection.meta == {}
    assert projection.meta_redacted is True
    assert projection.target_link is None


def test_split_event_wrapper_remains_under_the_reviewed_event_namespace():
    site = DynamicAuditSite("events/services_core.py", "wrapper", frozenset())
    assert site in discover_dynamic_audit_sites()
    assert WRAPPER_SITE_PREFIXES[site.path] == ("event.",)
    assert "events/services.py" not in WRAPPER_SITE_PREFIXES


def test_retired_link_removal_entry_is_gone_and_catalogue_is_exact():
    assert "organization.link_removed" not in discover_audit_meta_references().actions
    assert "organization.link_removed" not in PRESENTATION_CATALOG
    assert presentation_catalog_errors() == []
