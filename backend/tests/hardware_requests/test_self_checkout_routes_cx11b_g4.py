"""Public tool commands prove stock, scans, retained evidence and borrower attribution."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.boxes.models import QrCode, QrScanEvent
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.models import PublicToolLoan, ReturnEvent
from apps.hardware_requests.self_checkout_workflow import checkout_tool
from tests.hardware_requests.handout_support_cx11b_g4 import handout_world
from tests.operations.route_support_cx11b_g4 import cycle, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.self_checkout", "loans.enabled"])
@pytest.mark.parametrize("name", ["hardware_requests:public-tool-evidence-url", "hardware_requests:public-tool-checkout", "hardware_requests:public-tool-return"])
def test_self_checkout_route_performs_the_physical_evidence_workflow(native, key, name, monkeypatch):
    space, client, actor, product, issue, returned = handout_world(native, monkeypatch)
    qr = QrCode.objects.create(makerspace=space, target_type="product", target_id=product.pk)
    loan = checkout_tool(space, actor, qr.payload, evidence_id=issue.pk) if name == "hardware_requests:public-tool-return" else None
    monkeypatch.setattr("apps.hardware_requests.self_checkout_contact.presigned_upload",
        lambda key, mime, *, max_bytes, exact_bytes: {"url": "https://storage.example.test/upload", "fields": {"key": f"staging/{key}"}})
    body = {"payload": qr.payload, "evidence_id": returned.pk if loan else issue.pk, "remark": "All parts present"}
    if name == "hardware_requests:public-tool-evidence-url":
        body = {"evidence_type": "issue", "content_type": "image/jpeg", "size_bytes": 123}
    url = reverse(name, kwargs={"makerspace_slug": space.slug})
    before_photos = EvidencePhoto.objects.count()

    def check(response):
        if name == "hardware_requests:public-tool-evidence-url":
            photo = EvidencePhoto.objects.get(pk=response.data["evidence_id"])
            assert (photo.uploaded_by_id, photo.evidence_type, photo.size_bytes, photo.consumption_state) == (actor.pk, "issue", 123, "unconsumed")
            assert response.data["fields"]["key"] == f"staging/{photo.object_key}"
            assert EvidencePhoto.objects.count() == before_photos + 1
        elif name == "hardware_requests:public-tool-checkout":
            created = PublicToolLoan.objects.get(makerspace=space)
            assert (created.requester_id, created.qr_code_id, created.status, created.request.issue_evidence_id) == (actor.pk, qr.pk, "checked_out", issue.pk)
            assert QrScanEvent.objects.filter(request=created.request, qr_code=qr, actor=actor, context="issue").count() == 1
            product.refresh_from_db()
            assert (product.available_quantity, product.issued_quantity) == (9, 1)
            issue.refresh_from_db()
            assert issue.consumption_state == "consumed"
        else:
            loan.refresh_from_db()
            assert (loan.status, loan.return_evidence_id, loan.return_notes) == ("returned", returned.pk, "All parts present")
            event = ReturnEvent.objects.get(request=loan.request)
            assert (event.evidence_id, event.actor_id, event.remark) == (returned.pk, actor.pk, "All parts present")
            assert QrScanEvent.objects.filter(request=loan.request, qr_code=qr, actor=actor, context="return").count() == 1
            product.refresh_from_db()
            assert (product.available_quantity, product.issued_quantity) == (10, 0)
            returned.refresh_from_db()
            assert returned.consumption_state == "consumed"
    action = {"hardware_requests:public-tool-evidence-url": "evidence.upload_url_issued", "hardware_requests:public-tool-checkout": "public_tool.checked_out", "hardware_requests:public-tool-return": "public_tool.returned"}[name]
    # The account route requires sign-in; the public feature gate still precedes that
    # check. This intentionally preserves the public contract instead of applying 481.
    cycle(space, key, lambda: send(client, "POST", url, body), check,
          on=(200 if loan else 201, None), off=(404, "feature_disabled"), refusal_key="inventory.self_checkout",
          foreign=lambda: send(APIClient(), "POST", url, body),
          foreign_pair=lambda disabled: (404, "feature_disabled") if disabled else (401, "not_authenticated"), audit=(action,))
