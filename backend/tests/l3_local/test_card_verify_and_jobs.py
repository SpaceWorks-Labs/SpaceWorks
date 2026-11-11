"""L3 public card check (SPEC §7) and card jobs (#133)."""
import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.card_designs import jobs, tokens
from apps.card_designs.job_runner import run_chunk
from apps.card_designs.models import CardJob, CardVerifyCheckDay
from apps.makerspaces import member_card_services as services
from apps.makerspaces.models import MemberCardSettings
from tests.l3_local.helpers import card_space, client, manager, member

pytestmark = pytest.mark.django_db


def _space(slug):
    space = card_space(slug)
    MemberCardSettings.objects.update_or_create(makerspace=space, defaults={"public_verify": True})
    return space


def _check(token):
    from rest_framework.test import APIClient
    cache.clear()
    return APIClient().get(f"/api/v1/public/card-verifications/{token}")


def test_valid_card_check_headers_and_minimal_body():
    space = _space("cv-valid")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    response = _check(tokens.live("member_card", card).token)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == "valid" and body["valid"] is True and body["holder"] is None
    assert body["issuer"]["kind"] == "space" and "blood_group" not in str(body)
    assert response["X-Robots-Tag"] == "noindex, nofollow, noarchive"
    assert response["Cache-Control"] == "no-store" and response["Referrer-Policy"] == "no-referrer"
    assert CardVerifyCheckDay.objects.get(makerspace=space).count == 1


def test_opt_in_shows_name_and_revoked_shows_issuer_only():
    space = _space("cv-revoked")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    card.verify_show_name = True
    card.save(update_fields=["verify_show_name"])
    token = tokens.live("member_card", card).token
    assert _check(token).json()["holder"]["name"]
    services.revoke_card(sm, card, note="gone")
    body = _check(token).json()
    assert body["status"] == "revoked" and body["valid"] is False and body["number"] is None and body["holder"] is None


def test_reissued_card_reads_as_revoked_with_a_note():
    space = _space("cv-reissued")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    token = tokens.live("member_card", card).token
    services.reissue_card(sm, card, reason="damaged")
    body = _check(token).json()
    assert body["status"] == "revoked" and "newer card" in body["note"]


@pytest.mark.parametrize("case", ["unknown", "desk", "switched_off", "module_off"])
def test_uniform_404(case):
    space = _space(f"cv-404-{case}")
    sm = manager(space)
    card = services.issue_card(sm, member(space)[1])
    token = tokens.live("member_card", card).token
    if case == "unknown":
        token = "A" * 43
    elif case == "desk":
        token = services.active_qr(card).payload
    elif case == "switched_off":
        MemberCardSettings.objects.filter(makerspace=space).update(public_verify=False)
    else:
        space.enabled_modules = [key for key in space.enabled_modules if key != "membership"]
        space.save(update_fields=["enabled_modules"])
    response = _check(token)
    assert response.status_code == 404


def _cards(space, sm, count):
    return [services.issue_card(sm, member(space, f"j{index}")[1]) for index in range(count)]


def test_bulk_sheet_job_runs_in_chunks_and_only_the_requester_reads_it():
    space = card_space("cj-sheet")
    sm = manager(space)
    cards = _cards(space, sm, 3)
    job, created = jobs.enqueue(sm, space, "bulk_sheet", scope="member_cards", targets=[c.pk for c in cards],
                                params={"paper": "a4"})
    again, created_again = jobs.enqueue(sm, space, "bulk_sheet", scope="member_cards",
                                        targets=[c.pk for c in cards], params={"paper": "a4"})
    assert created and not created_again and again.pk == job.pk
    while run_chunk(job.pk):
        pass
    job.refresh_from_db()
    assert job.state == "succeeded" and job.done == 3 and job.result_key
    assert job.result_expires_at > timezone.now() + timezone.timedelta(days=6)
    assert client(sm).get(f"/api/v1/admin/card-jobs/{job.pk}").json()["download_ready"] is True
    assert "url" in client(sm).get(f"/api/v1/admin/card-jobs/{job.pk}/result").json()
    other = manager(space, "other")
    assert client(other).get(f"/api/v1/admin/card-jobs/{job.pk}").status_code == 404


def test_one_running_bulk_job_per_space_and_cancel():
    from rest_framework.exceptions import ValidationError
    space = card_space("cj-one")
    sm = manager(space)
    cards = _cards(space, sm, 2)
    first, _ = jobs.enqueue(sm, space, "zip", scope="member_cards", targets=[cards[0].pk])
    with pytest.raises(ValidationError):
        jobs.enqueue(sm, space, "bulk_per_person", scope="member_cards", targets=[cards[1].pk])
    jobs.cancel(sm, first)
    first.refresh_from_db()
    assert first.state == "cancelled" and run_chunk(first.pk) is False


def test_caps_refuse_oversized_jobs():
    from rest_framework.exceptions import ValidationError
    space = card_space("cj-cap")
    sm = manager(space)
    with pytest.raises(ValidationError):
        jobs.enqueue(sm, space, "zip", scope="member_cards", targets=list(range(1, 302)))


def test_switching_the_module_off_cancels_a_queued_job():
    space = card_space("cj-off")
    sm = manager(space)
    cards = _cards(space, sm, 1)
    job, _ = jobs.enqueue(sm, space, "bulk_per_person", scope="member_cards", targets=[cards[0].pk])
    space.enabled_modules = [key for key in space.enabled_modules if key != "membership"]
    space.save(update_fields=["enabled_modules"])
    assert run_chunk(job.pk) is False
    job.refresh_from_db()
    assert job.state == "cancelled" and job.error_code == "switched_off"


def test_zip_job_and_expired_results_are_purged():
    from apps.card_designs.tasks import purge_expired_card_job_results
    space = card_space("cj-zip")
    sm = manager(space)
    cards = _cards(space, sm, 2)
    job, _ = jobs.enqueue(sm, space, "zip", scope="member_cards", targets=[c.pk for c in cards])
    while run_chunk(job.pk):
        pass
    job.refresh_from_db()
    assert job.result_content_type == "application/zip"
    CardJob.objects.filter(pk=job.pk).update(result_expires_at=timezone.now() - timezone.timedelta(minutes=1))
    purge_expired_card_job_results()
    job.refresh_from_db()
    assert job.result_key == ""


def test_api_queues_member_card_jobs():
    space = card_space("cj-api")
    sm = manager(space)
    _cards(space, sm, 2)
    response = client(sm).post(f"/api/v1/admin/makerspaces/{space.pk}/member-card-jobs",
                               {"kind": "bulk_sheet", "status": "active"}, format="json")
    assert response.status_code == 201, response.content
    assert response.json()["total"] == 2


def test_new_template_revision_starts_a_fresh_bulk_output_without_rewriting_completed_history(monkeypatch):
    space = card_space("cj-template-revision")
    sm = manager(space)
    card = _cards(space, sm, 1)[0]
    job, _ = jobs.enqueue(sm, space, "bulk_sheet", scope="member_cards", targets=[card.pk])
    while run_chunk(job.pk):
        pass
    job.refresh_from_db()
    assert job.state == "succeeded"
    previous = (job.idempotency_key, job.result_key, job.result_size, job.finished_at)
    monkeypatch.setattr(jobs, "TEMPLATE_REVISION", jobs.TEMPLATE_REVISION + 1)
    updated, created = jobs.enqueue(sm, space, "bulk_sheet", scope="member_cards", targets=[card.pk])
    assert created and updated.pk != job.pk and updated.idempotency_key != job.idempotency_key
    job.refresh_from_db()
    assert job.state == "succeeded"
    assert (job.idempotency_key, job.result_key, job.result_size, job.finished_at) == previous
    jobs.cancel(sm, updated)


def test_published_custom_layout_remains_authoritative_when_shipped_defaults_change(monkeypatch):
    from copy import deepcopy
    from apps.card_designs import designs, resolution

    space = card_space("cj-custom-layout")
    sm = manager(space)
    design, _ = resolution.get_or_create(space, "member_cards", actor=sm, template="minimal")
    custom = deepcopy(design.document)
    text = next(layer for layer in custom["front"]["layers"] if layer["kind"] == "text")
    text["text"] = "Custom workshop card"
    design = designs.save(sm, design, custom, expected_revision=design.revision)
    design = designs.publish(sm, design)
    expected = deepcopy(design.published_document)
    def unexpected_default(_domain):
        raise AssertionError("A published custom document must not be replaced by a default")
    monkeypatch.setattr(resolution, "default_document", unexpected_default)
    resolved, owner = resolution.resolve(space.pk, "member_cards")
    assert owner.pk == design.pk and resolved == expected
    design.refresh_from_db()
    assert design.published_document == expected
