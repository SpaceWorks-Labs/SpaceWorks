"""Different card holders serialize the last wallet-pass slot at the HTTP seam."""
import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from apps.audit.models import AuditLog
from apps.card_designs.models import CardJob, WalletPass
from apps.card_designs.views_holder_photo import MyCardWalletView
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces import member_card_services
from tests.l3_local.helpers import card_space, client, manager, member
from tests.l3_local.test_wallet_service_conditions_246 import save_space
from tests.l3_local.wallet_material import google_material
from tests.makerspaces.test_daily_delivery_creator_races_cx7 import race

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership]


def world(settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    monkeypatch.setattr("apps.card_designs.tasks.dispatch", lambda *_: None)
    space = card_space("cx7-r4-wallet-request", features=("membership.wallet_passes",))
    actor = manager(space)
    save_space(actor, space, google_material())
    pairs = []
    for index in range(2):
        person, membership = member(space, name=f"wallet-holder-{index}")
        card = member_card_services.issue_card(actor, membership)
        pairs.append((client(person), card))
    space.resource_limit_overrides = {"wallet_passes": 1, "platform_wallet_monthly": 0}
    space.save(update_fields=["resource_limit_overrides"])
    def post(index):
        caller, card = pairs[index]
        return caller.post(reverse("member-card-wallet", kwargs={
            "kind": "member_card", "card_id": card.pk, "platform": "google"}), {}, format="json")
    return space, pairs, post


def snapshot(space):
    return [list(model.objects.filter(makerspace=space).order_by("pk").values())
            for model in (WalletPass, CardJob, AuditLog)]


def assert_one(space):
    assert WalletPass.objects.filter(makerspace=space).count() == 1
    assert CardJob.objects.filter(makerspace=space, kind="wallet_issue").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="card_job.queued").count() == 1


def test_wallet_max_next_and_replay_preserve_the_single_pass_job_and_audit(settings, monkeypatch):
    space, _, post = world(settings, monkeypatch)
    first = post(0)
    assert first.status_code == 201, first.data
    assert_one(space)
    before = snapshot(space)
    refused = post(1)
    assert (refused.status_code, refused.data["code"]) == (409, "wallet_passes_quota_reached")
    assert snapshot(space) == before
    repeated = post(0)
    assert repeated.status_code == 201, repeated.data
    assert repeated.data == first.data
    assert snapshot(space) == before
    assert_one(space)


@pytest.mark.django_db(transaction=True)
def test_different_valid_cards_racing_for_one_slot_create_one_pass_and_job(settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, _, post = world(settings, monkeypatch)
    responses = race(post)
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert [response.data["code"] for response in responses if response.status_code == 409] == [
        "wallet_passes_quota_reached"]
    assert_one(space)
    winner = next(index for index, response in enumerate(responses) if response.status_code == 201)
    before = snapshot(space)
    replay = post(winner)
    assert replay.status_code == 201
    assert replay.data == responses[winner].data
    assert snapshot(space) == before


def test_wallet_request_documents_its_actual_quota_conflict():
    schema = MyCardWalletView.post.kwargs["schema"]()
    view = MyCardWalletView()
    view.args, view.kwargs = (), {}
    view.request = view.initialize_request(APIRequestFactory().post("/"))
    schema.view, schema.method = view, "POST"
    response = schema.get_response_serializers()[409]
    assert response.response is ErrorSerializer
    assert response.description == "wallet_passes_quota_reached."


@pytest.mark.parametrize("field,key", [
    ("enabled_modules", "membership"), ("enabled_features", "membership.wallet_passes"),
])
def test_wallet_switches_keep_existing_rows_and_restore_the_same_job(settings, monkeypatch, field, key):
    space, _, post = world(settings, monkeypatch)
    first = post(0)
    assert first.status_code == 201, first.data
    before = snapshot(space)
    original = list(getattr(space, field))
    setattr(space, field, [value for value in original if value != key])
    space.save(update_fields=[field])
    refused = post(0)
    if field == "enabled_modules":
        assert (refused.status_code, refused.data["code"]) == (404, "not_found")
    else:
        assert (refused.status_code, refused.data["platform"].code) == (400, "invalid")
    assert snapshot(space) == before
    setattr(space, field, original)
    space.save(update_fields=[field])
    restored = post(0)
    assert restored.status_code == 201, restored.data
    assert restored.data == first.data
    assert snapshot(space) == before


def test_wallet_admission_uses_locked_space_limits_even_with_a_stale_card(settings, monkeypatch):
    from rest_framework.exceptions import APIException
    from apps.card_designs.wallet.service import request_pass
    from apps.makerspaces.models import Makerspace
    space, pairs, _ = world(settings, monkeypatch)
    card = pairs[0][1]
    card.makerspace = space
    Makerspace.objects.filter(pk=space.pk).update(resource_limit_overrides={"wallet_passes": 0})
    before = snapshot(space)
    with pytest.raises(APIException) as failure:
        request_pass(card.membership.user, "member_card", card, "google")
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (409, "wallet_passes_quota_reached")
    assert snapshot(space) == before
