"""U-C merge refusals: who can never merge, and a gated tenant."""

import pytest
from django.utils import timezone

from apps.accounts.account_merge_eligibility import account_refusal, resolve_source, source_refusal
from apps.accounts.models import User
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from tests.accounts.merge_helpers import (  # noqa: F401 -- fixtures
    client_for, converted, keys_and_clean_cache, outbox, person, proved_by_codes, space, start, url,
)

pytestmark = pytest.mark.django_db


def test_platform_and_walk_in_survivors_are_refused(outbox):
    root = User.objects.create_superuser("mr-root", "mr-root@example.test", "pw-strong-123")
    assert start(client_for(root), "anything").status_code in (401, 403)
    walk_in = person("mr-walkin", is_walk_in=True)
    refused = start(client_for(walk_in), "anything")
    assert refused.status_code == 403 and refused.data["code"] == "merge_not_allowed"


def test_ineligible_sources_resolve_to_nothing(outbox):
    survivor = person("mr-survivor")
    gone = converted("mr-deleted")
    User.objects.filter(pk=gone.pk).update(is_active=False, deletion_requested_at=timezone.now(),
                                           deletion_purge_after=timezone.now())
    inactive = converted("mr-inactive")
    User.objects.filter(pk=inactive.pk).update(is_active=False)
    restricted = converted("mr-restricted")
    User.objects.filter(pk=restricted.pk).update(access_status="restricted")
    plain = person("mr-plain")
    for account in (gone, inactive, restricted, plain):
        assert resolve_source(account.username, survivor) is None
    assert source_refusal(survivor, survivor) == "merge_not_allowed"
    self_converted = converted("mr-self")
    assert resolve_source(self_converted.username, self_converted) is None


def test_held_email_resolves_the_source(outbox):
    survivor = person("mr-held-survivor")
    source = converted("mr-held", held_email="held-address@example.test")
    assert resolve_source("HELD-address@example.test", survivor).pk == source.pk


def test_stubs_and_anonymous_requesters_are_refused():
    stub = person("mr-stub")
    User.objects.filter(pk=stub.pk).update(is_tenant_dump_stub=True)
    stub.refresh_from_db()
    assert account_refusal(stub) == "system_account"
    lab = space("mr-anon")
    from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
    assert account_refusal(get_or_create_anonymous_requester(lab)) is not None


def test_gated_tenant_refuses_confirm(outbox, monkeypatch):
    a = space("mr-gated")
    survivor, source = person("mr-gate-survivor"), converted("mr-gate-source", makerspace=a)
    client = client_for(survivor)
    intent = proved_by_codes(client, outbox, survivor, source.email, source.username)
    preview = client.get(url(intent, "preview")).data

    def gate(pk):
        if pk == a.pk:
            raise SourceMigrationGateClosed("frozen")

    monkeypatch.setattr("apps.tenant_migration.gate_runtime.assert_write_allowed", gate)
    refused = client.post(url(intent, "confirm"), {"preview_sha256": preview["preview_sha256"]}, format="json")
    assert refused.status_code == 409 and refused.data["code"] == "tenant_gated"
    assert User.objects.get(pk=source.pk).merged_into_id is None


def test_claim_sessions_never_reach_merge_routes():
    from apps.accounts.claim_route_types import Refused
    from apps.accounts.claim_routes import policy_for
    from apps.accounts.delegated_route_catalog import ACCOUNT_MERGE_ROUTES

    assert all(isinstance(policy_for(name, "POST"), Refused) for name in ACCOUNT_MERGE_ROUTES)
