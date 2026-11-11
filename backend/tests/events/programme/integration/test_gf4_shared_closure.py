"""Privacy and retained-custody regressions across the integrated lane boundaries."""
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.organizations import governance
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.member_organizations import MemberOrganizationsView
from apps.organizations.member_leave import MemberOrganizationLeaveView
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.events.collab_helpers import make_staff

pytestmark = pytest.mark.django_db


def request(view, actor, path, **kwargs):
    value = APIRequestFactory().get(path)
    force_authenticate(value, actor)
    return view.as_view()(value, **kwargs)


def test_own_organization_discovery_needs_no_host_membership_or_governor_access():
    owner, stranger = account("gf4-own-org"), account("gf4-other-org")
    own = Organization.objects.create(name="Own organization", slug="gf4-own-org")
    foreign = Organization.objects.create(name="Private organization", slug="gf4-foreign-org")
    OrganizationMembership.objects.create(organization=own, user=owner)
    OrganizationMembership.objects.create(organization=foreign, user=stranger)
    result = request(MemberOrganizationsView, owner, "/api/v1/member/organizations/")
    assert result.status_code == 200
    assert result["Cache-Control"] == "private, no-store"
    assert result.data["count"] == 1
    row = result.data["results"][0]
    assert row["id"] == own.pk and row["name"] == own.name
    assert row["leave_state"]["membership_version"] > 0
    assert row["leave_state"]["allowed_actions"] == ["leave"]
    assert set(row) == {"id", "name", "slug", "leave_state"}
    assert request(MemberOrganizationLeaveView, owner, "/leave/", pk=foreign.pk).status_code == 404


def test_sole_owner_leave_projection_changes_when_a_real_successor_exists():
    owner, successor = account("gf4-sole-owner"), account("gf4-successor")
    org = Organization.objects.create(name="Managed", slug="gf4-managed")
    OrganizationMembership.objects.create(organization=org, user=owner,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    result = request(MemberOrganizationLeaveView, owner, "/leave/", pk=org.pk)
    assert result.data["allowed_actions"] == [] and result.data["reason"] == "sole_owner"
    OrganizationMembership.objects.create(organization=org, user=successor,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    assert request(MemberOrganizationLeaveView, owner, "/leave/", pk=org.pk).data["allowed_actions"] == ["leave"]


def test_next_up_projection_is_scoped_and_contains_only_navigation_fields():
    from apps.operations.dashboard_programmes import _event_counts
    host, foreign = event_space("gf4-home"), event_space("gf4-foreign-home")
    actor = make_staff(host)
    local = open_event(host)
    open_event(foreign)
    rows = _event_counts(host, actor)["next_up_events"]
    assert [row["id"] for row in rows] == [local.pk]
    assert set(rows[0]) == {"id", "title", "starts_at", "ends_at", "href"}


def test_cleanup_custody_is_global_main_retention_but_not_portable_content():
    from apps.backup.main_projection_registry import table_rules, RowDisposition
    from apps.backup.object_ownership_registry import FIELD_OBJECT_RULES, ReferencePolicy
    from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
    from apps.tenant_migration.tenant_dump_types import ModelDisposition
    rules = {rule.model._meta.label: rule for rule in table_rules()}
    for label in ("events.EventAssetObligation", "events.BadgePrintCleanupReceipt"):
        assert rules[label].disposition == RowDisposition.RETAIN_GLOBAL
        assert FIRST_PARTY_MODEL_RULES[label].disposition == ModelDisposition.DROP
        objects = [rule for rule in FIELD_OBJECT_RULES if rule.model_label == label]
        assert objects and all(rule.policy == ReferencePolicy.COORDINATION_ONLY for rule in objects)
    assert rules["events.EventProgrammeSweepCursor"].disposition == RowDisposition.OMIT_OPERATIONAL


@pytest.mark.parametrize("role,field,label", [
    ("volunteer", "evidence", "EventContributionHours"),
    ("judge", "scores", "JudgeScore"),
])
def test_portable_work_proof_remaps_only_typed_ids_and_preserves_versions(role, field, label):
    from apps.tenant_migration.semantic_certificate_proof import remap_contribution_proof
    proof = {"version": 1, "role_assignment_id": 7, "role": role, field: [[11, 3]]}
    proof.update({"minutes": 60} if role == "volunteer" else {"ballots": []})
    seen = []
    def mapped(model, pk):
        seen.append((model, pk))
        return pk + 100
    value = remap_contribution_proof({"title": "Keep 11", "contribution_proof": proof}, mapped)
    assert value["title"] == "Keep 11" and proof[field] == [[11, 3]]
    assert value["contribution_proof"][field] == [[111, 3]]
    assert ("events." + label, 11) in seen


@pytest.mark.parametrize("kind,label", [("prizes", "HackathonPrize"), ("project_gallery", "GalleryEntry")])
def test_portable_page_options_remap_only_the_kind_specific_selector(kind, label):
    from apps.tenant_migration.semantic_events_programme import remap_programme
    source = {"kind": kind, "options": {"ids": [7], "layout": "grid", "limit": 12}}
    row = dict(source)
    seen = []
    def mapped(model, pk):
        seen.append((model, pk))
        return pk + 100
    remap_programme("events.EventPageSection", source, row, mapped)
    assert row["options"] == {"ids": [107], "layout": "grid", "limit": 12}
    assert source["options"]["ids"] == [7]
    assert seen == [("events." + label, 7)]


def test_portable_person_section_does_not_reuse_source_authorization_selectors():
    from apps.tenant_migration.semantic_events_programme import remap_programme
    row = {"kind": "mentors", "options": {"ids": [7], "layout": "list", "limit": 2}}
    remap_programme("events.EventPageSection", row, row, lambda *args: pytest.fail("No live person ID travels"))
    assert row["options"] == {"ids": [], "layout": "list", "limit": 2}


@pytest.mark.parametrize("options", [None, [], {"ids": [True]}, {"ids": [1, 1]}, {"limit": True}, {"layout": "script"}, {"unknown": 7}])
def test_portable_page_options_refuse_malformed_closed_schema(options):
    from apps.tenant_migration.semantic_events_programme import remap_programme
    row = {"kind": "prizes", "options": options}
    with pytest.raises(ValueError):
        remap_programme("events.EventPageSection", row, row, lambda label, pk: pk)


def test_portable_contribution_proof_refuses_boolean_schema_version():
    from apps.tenant_migration.semantic_certificate_proof import remap_contribution_proof
    with pytest.raises(ValueError):
        remap_contribution_proof({"contribution_proof": {"version": True}}, lambda label, pk: pk)


@pytest.mark.parametrize("layout", [None, [], {"contribution_proof": None}, {"contribution_proof": {"version": 1}}])
def test_portable_work_proof_refuses_malformed_layout_or_missing_identity(layout):
    from apps.tenant_migration.semantic_certificate_proof import remap_contribution_proof
    with pytest.raises(ValueError):
        remap_contribution_proof(layout, lambda label, pk: pk)
