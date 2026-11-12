"""Decision 246: the handover spine (evidence upload, box assignment, return, direct handout) for every built-in role.

Authority comes from `ROLE_CATALOG`: `upload_evidence`, `assign_box`, `return_request`, `issue_direct_loan`.
A refused call must change nothing (no status move, no quantity move, no audit row); an allowed call moves
stock exactly once; replays and malformed evidence are refused.
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.boxes.models import Box
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import (
    authenticated_client, make_accepted_request, make_issued_request, make_product, make_return_evidence,
    make_space, return_payload, return_url,
)
from tests.test_admin_direct_loans import direct_payload, direct_url, eligible_member

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]


def _can(slug, action):
    return action in ROLE_BY_SLUG[slug].granted_actions


@pytest.mark.parametrize("slug", SLUGS)
def test_evidence_upload_url_follows_upload_evidence(slug, monkeypatch):
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload",
                        lambda key, content_type: {"url": "http://minio/e", "fields": {"key": key}})
    space = make_space(f"hs-up-{slug}".replace("_", "-"))
    client = authenticated_client(staff_account(space, f"hs-up-actor-{slug}", slug))
    response = client.post(f"/api/v1/admin/makerspaces/{space.pk}/uploads/evidence-url",
                           {"evidence_type": "issue", "content_type": "image/png"}, format="json")
    assert (response.status_code in (200, 201)) is _can(slug, "upload_evidence"), response.content
    if not _can(slug, "upload_evidence"):
        assert response.status_code in (403, 404)


@pytest.mark.parametrize("body", [{}, {"evidence_type": "selfie", "content_type": "image/png"},
                                  {"evidence_type": "issue", "content_type": "application/x-msdownload"}])
def test_evidence_upload_validation_refuses_bad_type_and_mime(body):
    space = make_space("hs-upval")
    boss = authenticated_client(staff_account(space, "hs-upval-boss", "space_manager"))
    response = boss.post(f"/api/v1/admin/makerspaces/{space.pk}/uploads/evidence-url", body, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("slug", SLUGS)
def test_assign_box_follows_assign_box(slug):
    space = make_space(f"hs-box-{slug}".replace("_", "-"))
    request = make_accepted_request(space, make_product(space), 1)
    box = Box.objects.create(makerspace=space, label="Bin")
    client = authenticated_client(staff_account(space, f"hs-box-actor-{slug}", slug))
    response = client.post(f"/api/v1/admin/requests/{request.pk}/assign-box", {"box_code": box.code}, format="json")
    request.refresh_from_db()
    if _can(slug, "assign_box"):
        assert response.status_code == 200, response.content
        assert request.assigned_box_id == box.pk
    else:
        assert response.status_code in (403, 404)
        assert request.assigned_box_id is None


@pytest.mark.parametrize("slug", SLUGS)
def test_return_follows_return_request_and_moves_stock_once(slug):
    space = make_space(f"hs-ret-{slug}".replace("_", "-"))
    product = make_product(space, total_quantity=5, available_quantity=5)
    boss = staff_account(space, f"hs-ret-boss-{slug}", "space_manager")
    request = make_issued_request(space, boss, [(product, 2)])
    evidence = make_return_evidence(space, boss)
    actor = staff_account(space, f"hs-ret-actor-{slug}", slug)
    client = authenticated_client(actor)
    first = client.post(return_url(request), return_payload(request, evidence), format="json")
    request.refresh_from_db()
    product.refresh_from_db()
    if _can(slug, "return_request"):
        assert first.status_code == 200, first.content
        assert request.status == HardwareRequest.Status.RETURNED
        assert (product.available_quantity, product.issued_quantity) == (5, 0)
        again = client.post(return_url(request), return_payload(request, make_return_evidence(space, boss)),
                            format="json")
        assert again.status_code in (400, 409)
        product.refresh_from_db()
        assert (product.available_quantity, product.issued_quantity) == (5, 0)
    else:
        assert first.status_code in (403, 404)
        assert request.status == HardwareRequest.Status.ISSUED
        assert (product.available_quantity, product.issued_quantity) == (3, 2)
        assert not AuditLog.objects.filter(makerspace=space, actor=actor).exists()


@pytest.mark.parametrize("mutate", [lambda p: p.pop("remark"), lambda p: p.update(remark=""),
                                    lambda p: p.pop("evidence_id"), lambda p: p.update(evidence_id=99999999),
                                    lambda p: p.update(box_code="WRONG-BOX"), lambda p: p.update(resolutions=[])])
def test_a_return_without_remark_photo_matching_box_or_resolutions_is_refused(mutate):
    space = make_space("hs-retval")
    product = make_product(space)
    boss = staff_account(space, "hs-retval-boss", "space_manager")
    request = make_issued_request(space, boss, [(product, 1)])
    body = return_payload(request, make_return_evidence(space, boss))
    mutate(body)
    response = authenticated_client(boss).post(return_url(request), body, format="json")
    assert response.status_code in (400, 404, 409)
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ISSUED


def test_another_spaces_staff_and_anonymous_cannot_return():
    mine, theirs = make_space("hs-ret-iso-a"), make_space("hs-ret-iso-b")
    boss = staff_account(mine, "hs-ret-iso-boss", "space_manager")
    request = make_issued_request(mine, boss, [(make_product(mine), 1)])
    body = return_payload(request, make_return_evidence(mine, boss))
    outsider = authenticated_client(staff_account(theirs, "hs-ret-iso-out", "space_manager"))
    assert outsider.post(return_url(request), body, format="json").status_code in (403, 404)
    assert APIClient().post(return_url(request), body, format="json").status_code in (401, 403)
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ISSUED


@pytest.mark.parametrize("slug", SLUGS)
def test_direct_handout_follows_issue_direct_loan(slug):
    space = make_space(f"hs-dl-{slug}".replace("_", "-"))
    product = make_product(space, total_quantity=3, available_quantity=3, is_public=True)
    borrower = eligible_member(space)
    actor = staff_account(space, f"hs-dl-actor-{slug}", slug)
    response = authenticated_client(actor).post(
        direct_url(space),
        direct_payload(makerspace=space, borrower=borrower, items=[{"product_id": product.pk, "quantity": 1}]),
        format="json")
    product.refresh_from_db()
    if _can(slug, "issue_direct_loan"):
        assert response.status_code == 201, response.content
        assert (product.available_quantity, product.issued_quantity) == (2, 1)
        assert PublicToolLoan.objects.filter(makerspace=space).count() == 1
    else:
        assert response.status_code in (403, 404)
        assert (product.available_quantity, product.issued_quantity) == (3, 0)
        assert not PublicToolLoan.objects.exists()


@pytest.mark.parametrize("override", [{"items": []}, {"items": [{"product_id": 99999999, "quantity": 1}]},
                                      {"evidence_id": None}, {"borrower_id": 99999999}])
def test_direct_handout_needs_items_evidence_and_a_real_borrower(override):
    space = make_space("hs-dlval")
    product = make_product(space)
    boss = staff_account(space, "hs-dlval-boss", "space_manager")
    body = direct_payload(makerspace=space, borrower=eligible_member(space),
                          items=[{"product_id": product.pk, "quantity": 1}])
    body.update(override)
    if body.get("evidence_id") is None:
        body.pop("evidence_id")
    response = authenticated_client(boss).post(direct_url(space), body, format="json")
    # An unknown borrower is a uniform 403 (decision 223: `_borrower_for_makerspace` does not reveal whether
    # the account exists, it only says that nobody here may be handed items under that id).
    assert response.status_code in ((400, 404, 409, 403) if "borrower_id" in override else (400, 404, 409))
    product.refresh_from_db()
    assert product.issued_quantity == 0 and not PublicToolLoan.objects.exists()


def test_direct_handout_cannot_issue_more_than_stock_or_use_another_spaces_product():
    mine, theirs = make_space("hs-dlq-a"), make_space("hs-dlq-b")
    boss = authenticated_client(staff_account(mine, "hs-dlq-boss", "space_manager"))
    scarce = make_product(mine, total_quantity=2, available_quantity=2)
    foreign = make_product(theirs, name="Theirs")
    borrower = eligible_member(mine)
    over = boss.post(direct_url(mine), direct_payload(makerspace=mine, borrower=borrower,
                     items=[{"product_id": scarce.pk, "quantity": 5}]), format="json")
    cross = boss.post(direct_url(mine), direct_payload(makerspace=mine, borrower=borrower,
                      items=[{"product_id": foreign.pk, "quantity": 1}]), format="json")
    assert over.status_code in (400, 409) and cross.status_code in (400, 404)
    scarce.refresh_from_db()
    foreign.refresh_from_db()
    assert scarce.issued_quantity == 0 and foreign.issued_quantity == 0
