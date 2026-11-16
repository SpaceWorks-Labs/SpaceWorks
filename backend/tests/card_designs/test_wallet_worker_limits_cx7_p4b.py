"""Queued wallet jobs recheck platform signing capacity at the actual issue seam."""
import pytest
from django.db import connection, transaction
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.card_designs.models import CardJob, WalletPass
from apps.card_designs.wallet.service import issue_from_job, request_pass
from apps.makerspaces import member_card_services
from tests.l3_local.helpers import card_space, manager, member
from tests.l3_local.test_wallet_service_conditions_246 import save_platform, save_space
from tests.l3_local.wallet_material import apple_material, google_material
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership]


def setup(monkeypatch, own=False, platform="google"):
    monkeypatch.setattr("apps.card_designs.tasks.dispatch", lambda *_: None)
    monkeypatch.setattr("apps.card_designs.storage.put_bytes", lambda *args: None)
    monkeypatch.setattr("apps.card_designs.wallet.apple.build_pkpass", lambda *args: b"test-pkpass")
    space = card_space("cx7-p4b-wallet", features=("membership.wallet_passes",))
    actor = manager(space)
    save_platform(actor, {**google_material(), **apple_material()})
    if own:
        save_space(actor, space, google_material(issuer="3388000000099999999"))
    jobs = []
    for index in range(2):
        person, membership = member(space, name=f"holder-{index}")
        card = member_card_services.issue_card(actor, membership)
        with transaction.atomic():
            selected = ("apple" if index == 0 else "google") if platform == "mixed" else platform
            row, job = request_pass(person, "member_card", card, selected)
        assert job.params == {"platform": selected, "pass_id": row.pk}
        jobs.append(job)
    space.resource_limit_overrides = {"platform_wallet_monthly": 0 if own else 1}
    space.save(update_fields=["resource_limit_overrides"])
    return space, jobs


def snapshot():
    return [list(model.objects.order_by("pk").values()) for model in (WalletPass, CardJob, AuditLog)]


@pytest.mark.parametrize("platform", ["apple", "google", "mixed"])
def test_wallet_worker_max_next_exact_refusal_keeps_queued_pass_untouched(platform, monkeypatch):
    space, jobs = setup(monkeypatch, platform=platform)
    assert issue_from_job(jobs[0]) is True
    before = snapshot()
    with pytest.raises(APIException) as failure:
        issue_from_job(jobs[1])
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "platform_wallet_limit_reached")
    assert snapshot() == before
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued", meta__source="platform").count() == 1
    if platform == "google":
        jobs[0].refresh_from_db()
        assert jobs[0].params["save_url"].startswith("https://pay.google.com/gp/v/save/")
    else:
        assert jobs[0].parts == [f"card-jobs/{space.pk}/{jobs[0].pk}/pass.pkpass"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("platform", ["apple", "google", "mixed"])
def test_two_wallet_workers_for_different_holders_have_one_platform_slot(platform, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, jobs = setup(monkeypatch, platform=platform)
    assert race_creators(lambda index: issue_from_job(jobs[index])) == [
        (201, "created"), (400, "platform_wallet_limit_reached")]
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued", meta__source="platform").count() == 1
    assert WalletPass.objects.filter(makerspace=space, content_digest="").count() == 1


def test_wallet_own_credentials_remain_independent_of_platform_zero(monkeypatch):
    space, jobs = setup(monkeypatch, own=True)
    assert [issue_from_job(job) for job in jobs] == [True, True]
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued", meta__source="space").count() == 2
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued", meta__source="platform").count() == 0


def test_wallet_switch_off_keeps_queued_jobs_then_on_issues_at_last_slot(monkeypatch):
    space, jobs = setup(monkeypatch)
    saved = space.enabled_features
    space.enabled_features = [key for key in saved if key != "membership.wallet_passes"]
    space.save(update_fields=["enabled_features"])
    before = snapshot()
    assert issue_from_job(jobs[0]) is False
    assert snapshot() == before
    space.enabled_features = saved
    space.save(update_fields=["enabled_features"])
    assert issue_from_job(jobs[0]) is True


def test_already_signed_pass_reissue_is_not_a_new_platform_slot(monkeypatch):
    space, jobs = setup(monkeypatch)
    assert issue_from_job(jobs[0]) is True
    space.resource_limit_overrides = {"platform_wallet_monthly": 0}
    space.save(update_fields=["resource_limit_overrides"])
    assert issue_from_job(jobs[0]) is True
    assert WalletPass.objects.filter(makerspace=space).count() == 2
    from apps.managed_hosting.platform_limits import platform_used
    assert platform_used(space, "platform_wallet_monthly") == 1
