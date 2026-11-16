"""529.1: valid POST, PUT and pre-release evidence never needs a pre-existing sidecar."""
import pytest
from django.db import connection, transaction

from apps.audit.models import AuditLog
from apps.evidence import storage
from apps.evidence.finalization import charge_storage_once
from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.makerspaces.models import Makerspace
from tests.handout_roles import make_handout_member
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import authenticated_client, make_space, make_return_evidence, return_payload, return_url
from tests.test_admin_direct_loans import direct_payload, direct_url, eligible_member
from tests.test_issue import assign_scanned_box, issue_url, make_accepted_request, make_box, make_issue_evidence, make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_evidence_uploads]


@pytest.fixture(params=["post", "put", "legacy"])
def world(request, settings, monkeypatch):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.MANAGED_PLANS_ENABLED = False
    settings.STORAGE_PRESIGN_METHOD = "post" if request.param == "legacy" else request.param
    # The consumer has validated bytes; older/POST evidence may have no promotion
    # sidecar, whereas PUT promotion normally created it before attachment.
    space = make_space("r2-evidence-sidecar")
    actor = make_handout_member("r2-evidence-handover", space)
    def validated(photo, maximum):
        if request.param == "put":
            EvidenceUploadFinalization.objects.get_or_create(evidence=photo, defaults={
                "status": "finalized", "size_bytes": 123, "content_type": "image/jpeg"})
        return storage.EvidenceValidationResult(size=123, content_type="image/jpeg")
    monkeypatch.setattr(storage, "finalize_upload", validated)
    return space, actor, authenticated_client(actor)


def assert_once(space, photos, metadata):
    for photo in photos:
        row = EvidenceUploadFinalization.objects.get(evidence=photo)
        assert (row.status, row.quota_charged, row.size_bytes) == ("finalized", True, 123)
        charge_storage_once(photo, 123)
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 123 * len(photos)
    after = list(EvidencePhoto.objects.filter(pk__in=[p.pk for p in photos]).order_by("pk").values())
    for row in after:
        assert row.pop("consumption_state") == "consumed"
    assert after == [{key: value for key, value in row.items() if key != "consumption_state"} for row in metadata]


def test_issue_and_return_with_valid_evidence_charge_each_photo_once(world):
    space, actor, api = world
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    assign_scanned_box(request, make_box(space), actor)
    issue = make_issue_evidence(space, actor)
    returned = make_return_evidence(space, actor)
    photos = [issue, returned]
    metadata = list(EvidencePhoto.objects.filter(pk__in=[p.pk for p in photos]).order_by("pk").values())
    response = api.post(issue_url(request), {"evidence_id": issue.pk, "remark": "Handed over"}, format="json")
    assert response.status_code == 200, response.data
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ISSUED
    response = api.post(return_url(request), return_payload(request, returned), format="json")
    assert response.status_code == 200, response.data
    request.refresh_from_db()
    product.refresh_from_db()
    assert request.status == HardwareRequest.Status.RETURNED
    assert (product.issued_quantity, product.available_quantity, product.reserved_quantity) == (0, 5, 0)
    assert_once(space, photos, metadata)
    assert AuditLog.objects.filter(makerspace=space, action="request.issued").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="request.returned").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="evidence.attached").count() == 2


def test_direct_handout_with_valid_evidence_charges_once_without_a_sidecar(world):
    space, actor, api = world
    photo = make_issue_evidence(space, actor)
    product = make_product(space)
    metadata = list(EvidencePhoto.objects.filter(pk=photo.pk).values())
    response = api.post(direct_url(space), direct_payload(
        makerspace=space, borrower=eligible_member(space), evidence_id=photo.pk,
        items=[{"product_id": product.pk, "quantity": 1}],
    ), format="json")
    assert response.status_code == 201, response.data
    assert PublicToolLoan.objects.get(makerspace=space).request.status == HardwareRequest.Status.ISSUED
    product.refresh_from_db()
    assert (product.issued_quantity, product.available_quantity) == (1, 4)
    assert_once(space, [photo], metadata)
    assert AuditLog.objects.filter(makerspace=space, action="evidence.attached").count() == 1


def test_missing_sidecar_creation_and_charge_roll_back_with_a_failed_consumer(world):
    space, actor, _ = world
    photo = make_issue_evidence(space, actor)
    with transaction.atomic():
        charge_storage_once(photo, 123)
        transaction.set_rollback(True)
    assert not EvidenceUploadFinalization.objects.filter(evidence=photo).exists()
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 0
    charge_storage_once(photo, 123)
    charge_storage_once(photo, 123)
    assert EvidenceUploadFinalization.objects.get(evidence=photo).quota_charged is True
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 123


@pytest.mark.django_db(transaction=True)
def test_two_first_consumers_create_one_sidecar_and_charge_once(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("r2-evidence-first-charge-race")
    actor = make_handout_member("r2-evidence-first-charge", space)
    photo = make_issue_evidence(space, actor)
    assert race_creators(lambda _: charge_storage_once(photo, 123)) == [(201, "created"), (201, "created")]
    assert EvidenceUploadFinalization.objects.filter(evidence=photo, quota_charged=True).count() == 1
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 123


def test_missing_sidecar_never_substitutes_for_uploaded_evidence(world, monkeypatch):
    space, actor, api = world
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    assign_scanned_box(request, make_box(space), actor)
    photo = make_issue_evidence(space, actor)
    monkeypatch.setattr(storage, "finalize_upload", lambda *a: None)
    before = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    response = api.post(issue_url(request), {"evidence_id": photo.pk, "remark": "No upload"}, format="json")
    assert (response.status_code, response.data["code"]) == (409, "evidence_not_uploaded")
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ACCEPTED
    assert not EvidenceUploadFinalization.objects.filter(evidence=photo).exists()
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 0
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == before
