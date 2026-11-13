from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import transaction, connections
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_public_pages import MakerspacePublicPage
from apps.makerspaces.public_page_assets import charge_storage
from apps.makerspaces.public_page_contract import empty_document
from apps.organizations.models import Organization
from apps.organizations.models_public_pages import OrganizationPublicPageStorage
from apps.tenant_migration.source_gate import claim
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from tests.public_pages.l1b_threads import database_worker, wait_for_blocked
from tests.tenant_migration.source_gate_helpers import make_actor

pytestmark = pytest.mark.django_db(transaction=True)


def test_page_save_rechecks_authority_after_concurrent_revocation(page_owner):
    space, actor = page_owner
    def save():
        return pages.save("makerspace", space.pk, actor=actor, version=0, document=empty_document("makerspace"))
    # Keep the worker alive beyond the transaction holding its contested lock.
    from contextlib import ExitStack
    with ExitStack() as stack:
        with transaction.atomic():
            membership = MakerspaceMembership.staff_tracks.select_for_update().get(makerspace=space, user=actor)
            future, pid = stack.enter_context(database_worker(save))
            wait_for_blocked(pid)
            membership.status = "revoked"
            membership.save(update_fields=["status"])
        with pytest.raises(PermissionDenied):
            future.result(timeout=15)
    assert not MakerspacePublicPage.objects.filter(makerspace=space).exists()


def test_source_freeze_wins_before_blocked_page_write(page_owner):
    space, actor = page_owner
    platform = make_actor("page-freeze")
    from contextlib import ExitStack
    with ExitStack() as stack:
        with transaction.atomic():
            claim(space, platform)
            future, pid = stack.enter_context(database_worker(lambda: pages.save("makerspace", space.pk,
                actor=actor, version=0, document=empty_document("makerspace"))))
            wait_for_blocked(pid)
        with pytest.raises(SourceMigrationGateClosed):
            future.result(timeout=15)
    assert not MakerspacePublicPage.objects.filter(makerspace=space).exists()


def test_organization_storage_reservations_serialize_at_fixed_global_cap():
    org = Organization.objects.create(name="Global quota", slug="quota-race")
    barrier = Barrier(2)
    def reserve():
        connections.close_all()
        try:
            barrier.wait(timeout=5)
            with transaction.atomic():
                owner = Organization.objects.select_for_update().get(pk=org.pk)
                charge_storage("organization", owner, 60_000_000)
            return "reserved"
        except ValidationError:
            return "full"
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(reserve) for _ in range(2)]
        results = sorted(job.result(timeout=15) for job in jobs)
    assert results == ["full", "reserved"]
    assert OrganizationPublicPageStorage.objects.get(organization=org).used_bytes == 60_000_000
