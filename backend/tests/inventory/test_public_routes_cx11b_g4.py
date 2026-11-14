"""Public reads retain seeded content; public access is deliberately independent of staff standing."""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.inventory.models import Category
from apps.makerspaces.models import Makerspace
from tests.modules.switch_matrix_object_helpers import object_world, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes
from tests.operations.route_support_cx11b_g4 import contains, cycle, snapshot
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["public_inventory", "loans.enabled"])
@pytest.mark.parametrize("name", ["v1:public-inventory", "v1:public-inventory-detail", "v1:public-inventory-categories"])
def test_public_catalogue_reads_the_same_seed_after_each_gate_restores(native, key, name):
    space, client, _ = object_world(native)
    space.public_site_enabled = space.public_inventory_enabled = True
    space.save(update_fields=["public_site_enabled", "public_inventory_enabled"])
    category = Category.objects.create(makerspace=space, name="Electronics", slug="electronics")
    product = make_product(space, name="Retained multimeter", category=category)
    hidden = make_product(space, name="Private shelf item", is_public=False)
    kwargs = {"makerspace_slug": space.slug}
    if name.endswith("detail"):
        kwargs["pk"] = product.pk
    url = reverse(name, kwargs=kwargs)

    def check(response):
        if name.endswith("detail"):
            assert (response.data["id"], response.data["name"]) == (product.pk, "Retained multimeter")
        else:
            contains(response, category.pk if name.endswith("categories") else product.pk)
        for private in ("storage_location", "box_id", "qr_code", "scan_history", "evidence_photos"):
            assert private not in str(response.data)

    # Public read contract: AllowAny. Same content is available without a staff grant.
    anonymous = APIClient()
    cycle(space, key, lambda: client.get(url), check, refusal_key="public_inventory",
          foreign=lambda: anonymous.get(url),
          foreign_pair=lambda disabled: (404, "module_disabled") if disabled else (200, None))
    assert response_pair(anonymous.get(reverse("v1:public-inventory-detail", kwargs={
        "makerspace_slug": space.slug, "pk": hidden.pk}))) == (404, "not_found")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_public_directory_publication_hides_then_restores_the_exact_space(native):
    space, client, _ = object_world(native)
    space.public_site_enabled = True
    space.save(update_fields=["public_site_enabled"])
    if native:
        client._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
    from apps.accounts.models import User
    from apps.makerspaces.public_profile_handles import ensure_default_handle
    ensure_default_handle(User.objects.get(username="sx-real-object-manager"))
    url = reverse("v1:public-makerspaces")
    from apps.audit.models import AuditLog
    from apps.tenant_rls.capabilities import reset_sampling
    # The public directory intentionally audits its cross-tenant RLS capability.
    # Prove that first-use audit explicitly before measuring inert domain reads.
    reset_sampling()
    audit_before = list(AuditLog.objects.values_list("pk", flat=True))
    assert response_pair(client.get(url)) == (200, None)
    security_audit = AuditLog.objects.exclude(pk__in=audit_before).get()
    assert security_audit.action == "rls.capability_used"
    assert security_audit.meta == {"capability": "public_directory", "path": "public-makerspaces", "actor_kind": "anonymous"}
    before = snapshot()
    retained = Makerspace.objects.filter(pk=space.pk).values().get()
    retained.pop("public_site_enabled")
    for visible in (True, False, True):
        space.public_site_enabled = visible
        space.save(update_fields=["public_site_enabled"])
        cache.clear()
        # Configuration changes can emit audit rows; the HTTP read itself is inert.
        before = snapshot()
        with no_domain_writes():
            response = client.get(url)
        assert response_pair(response) == (200, None)
        assert [row["slug"] for row in response.data] == ([space.slug] if visible else [])
        current = snapshot()
        assert current == before
        stored = Makerspace.objects.filter(pk=space.pk).values().get()
        assert stored.pop("public_site_enabled") is visible
        assert stored == retained
    assert snapshot() == before
    # This is a public directory, so a caller without any standing gets the same list.
    assert APIClient().get(url).data == response.data


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["public_inventory", "loans.enabled"])
def test_public_stats_hides_the_only_section_and_restores_exact_library(native, key):
    space, client, _ = object_world(native)
    space.public_site_enabled = space.public_inventory_enabled = space.public_stats_enabled = True
    space.public_stats_sections = "lending"
    space.save(update_fields=["public_site_enabled", "public_inventory_enabled", "public_stats_enabled", "public_stats_sections"])
    for index in range(3):
        make_product(space, name=f"Retained library item {index}")
    url = reverse("v1:public-makerspace-stats", kwargs={"makerspace_slug": space.slug})

    def check(response):
        assert response.data["sections"] == ["lending"]
        assert response.data["hardware"]["library"]["library_size"] == 3
        assert next(row for row in response.data["metrics"] if row["key"] == "lending.library")["value"] == 3
    cycle(space, key, lambda: client.get(url), check, off=(404, "not_found"),
          foreign=lambda: APIClient().get(url),
          foreign_pair=lambda disabled: (404, "not_found") if disabled else (200, None))
