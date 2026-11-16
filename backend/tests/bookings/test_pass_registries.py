from copy import deepcopy

import pytest
from django.urls import reverse, resolve
from django.utils import timezone

from apps.accounts.claim_routes_public import PUBLIC_CLAIM_ROUTES
from apps.accounts.claim_route_types import Refused
from apps.apiclients.scope_registry import lookup
from apps.bookings.models import BookableSpace
from apps.bookings.pass_templates import DEFAULT_PASS_TEMPLATE
from apps.data_export.classification import EXPORTED_MODEL_FIELDS
from apps.data_export.references_json_fields import JSON_REFERENCE_FIELDS
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.confirmation_privacy import _PRIVATE_PATH
from apps.makerspaces.origin_scope_model_lookups import BASE_MODEL_LOOKUPS
from apps.makerspaces.origin_scope_routes import PUBLIC_SLUG_ROUTES
from apps.makerspaces.setup_areas import features_for
from apps.tenant_migration.tenant_dump_authority import AUTHORITY_FIELD_OVERRIDES
from apps.tenant_migration.tenant_dump_catalog import CATALOG_SCHEMA_SHA256, schema_digest
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition


def test_pass_field_has_full_portability_and_no_new_authority_or_object_edges():
    assert "pass_template" in EXPORTED_MODEL_FIELDS["bookings.BookableSpace"].split()
    assert ("bookings.BookableSpace", "pass_template") in JSON_REFERENCE_FIELDS
    policy = AUTHORITY_FIELD_OVERRIDES[("bookings.BookableSpace", "pass_template")]
    assert policy.dispositions == (AuthorityDisposition.PRESERVE,)
    assert schema_digest() == CATALOG_SCHEMA_SHA256
    field = BookableSpace._meta.get_field("pass_template")
    assert not field.is_relation


def test_installer_parent_and_prerequisite():
    feature = FEATURES["bookings.passes"]
    assert feature.parent_module == "bookings" and not feature.default_enabled
    assert feature.requires_modules == ("bookings",)
    assert feature.requires_features == ("bookings.confirmations",)
    assert "bookings.passes" in features_for({"bookings"})
    assert "bookings.passes" not in features_for({"events"})


@pytest.mark.parametrize("route,suffix", [
    ("admin-booking-pass-template", "pass-template/"),
    ("admin-booking-pass-preview", "pass-preview/"),
    ("admin-booking-pass", "arrival/12/pass/"),
])
def test_staff_origin_targets_and_private_failure_headers(route, suffix):
    kwargs = {"pk": 7, **({"booking_id": 12} if route == "admin-booking-pass" else {})}
    path = reverse(route, kwargs=kwargs)
    assert resolve(path).url_name == route
    assert path == "/api/v1/admin/spaces/7/" + suffix and _PRIVATE_PATH.fullmatch(path)
    assert BASE_MODEL_LOOKUPS[route] == ("bookings.BookableSpace", "makerspace_id")


def test_member_scope_and_claim_policy():
    assert "member-booking-pass" in PUBLIC_SLUG_ROUTES
    for method in ("GET", "HEAD"):
        entry = lookup("member-booking-pass", method)
        assert entry is not None and not entry.legacy_v1 and not entry.tenant_apps_admitted
        assert isinstance(PUBLIC_CLAIM_ROUTES[("member-booking-pass", method)], Refused)


@pytest.mark.django_db(transaction=True)
def test_layout_clone_and_uninstall_purge_are_tenant_local(monkeypatch):
    from apps.accounts.models import User
    from apps.bookings.services_clone import clone_space
    from apps.bookings.services_passes import save_pass_template
    from apps.makerspaces.lifecycle_purge import purge
    from apps.makerspaces.module_install import uninstall_module
    from apps.makerspaces.module_purge import purge_module
    from tests.bookings.pass_helpers import pass_world
    from tests.bookings.staff_grant_helpers import grant_fixture
    w = pass_world(monkeypatch, permission="edit_details", arrived=False)
    save_pass_template(w.resource, DEFAULT_PASS_TEMPLATE, actor=w.grantee)
    clone = clone_space(w.resource, actor=w.actor)
    assert clone.pass_template == DEFAULT_PASS_TEMPLATE
    clone.pass_template["elements"][0]["font_size_pt"] = 10
    clone.save(update_fields=["pass_template"])
    w.resource.refresh_from_db()
    assert w.resource.pass_template == DEFAULT_PASS_TEMPLATE
    other, _, _, foreign, _, _ = grant_fixture(slug="pass-purge-other")
    foreign.pass_template = deepcopy(DEFAULT_PASS_TEMPLATE)
    foreign.save(update_fields=["pass_template"])
    root = User.objects.create_superuser(username="pass-purge-root", email="root@example.test", password="pw")
    uninstall_module(w.tenant, "bookings")
    assert BookableSpace.objects.get(pk=w.resource.pk).pass_template == DEFAULT_PASS_TEMPLATE
    purge_module(w.tenant, "bookings", root)
    assert not BookableSpace.objects.filter(makerspace=w.tenant).exists()
    assert BookableSpace.objects.get(pk=foreign.pk).pass_template == DEFAULT_PASS_TEMPLATE
    other.archived_at = timezone.now()
    other.save(update_fields=["archived_at"])
    purge(other, root)
    assert not BookableSpace.objects.filter(pk=foreign.pk).exists()
