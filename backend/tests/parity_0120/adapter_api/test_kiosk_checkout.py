"""checkout.kiosk: the device is only a terminal for the existing self-checkout workflow; no Hard Rule is bypassed."""
import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.boxes.models import QrCode
from apps.evidence.storage import EvidenceValidationResult
from apps.hardware_requests.models import PublicToolLoan
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.return_helpers import make_issue_evidence, make_product
from tests.test_public_self_checkout import eligible_member

pytestmark = pytest.mark.django_db(transaction=True)
NFC = "04A1B2C3D4"


@pytest.fixture(autouse=True)
def storage(monkeypatch, settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        lambda evidence, max_bytes: EvidenceValidationResult(size=123, content_type="image/png"))
    monkeypatch.setattr("apps.hardware_requests.self_checkout_contact.presigned_upload",
                        lambda key, content_type: {"url": "https://storage.test/upload", "fields": {}})


def kiosk(slug, *, public=True):
    case = adapter_case(slug, caps=("status", "events"), extra=("checkout.kiosk",))
    space = case["space"]
    member = eligible_member(space, username=f"{slug}-member")
    case["client"].post(reverse("devices:admin-adapter-credentials", args=[space.pk]),
                        {"user_id": member.pk, "kind": "nfc", "secret": NFC}, format="json")
    product = make_product(space, public_self_checkout_enabled=public)
    qr = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.PRODUCT, target_id=product.pk)
    shelf = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]),
                                {"target_type": "space", "external_ref": "front-desk", "capabilities": ["checkout.kiosk"]},
                                format="json")
    assert shelf.status_code == 201, shelf.data
    case.update(member=member, qr=qr, product=product, kiosk_binding=shelf.data["id"])
    return case


def start(case, value=NFC):
    return case["sim"].post("kiosk/sessions", {"binding_id": case["kiosk_binding"],
                                              "credential": {"type": "nfc", "value": value}})


def step(case, sid, name, data):
    return case["sim"].post(f"kiosk/sessions/{sid}/{name}", data)


def upload(case, sid, kind):
    response = step(case, sid, "evidence", {"evidence_type": kind, "content_type": "image/png"})
    assert response.status_code == 201, response.data
    return response.data["evidence_id"]


def test_issue_and_return_run_through_the_self_checkout_workflow_with_evidence():
    case = kiosk("kiosk-flow")
    opened = start(case)
    assert opened.status_code == 201 and opened.data["allowed"] is True
    sid = opened.data["session_id"]
    assert step(case, sid, "scan", {"qr_payload": case["qr"].payload}).data["action"] == "checkout"
    issued = step(case, sid, "issue", {"qr_payload": case["qr"].payload, "evidence_id": upload(case, sid, "issue")})
    assert issued.status_code == 201, issued.data
    loan = PublicToolLoan.objects.get(makerspace=case["space"])
    assert loan.status == "checked_out" and loan.requester_id == case["member"].pk and loan.request.issue_evidence_id
    assert step(case, sid, "scan", {"qr_payload": case["qr"].payload}).data["action"] == "return"
    returned = step(case, sid, "return", {"qr_payload": case["qr"].payload, "evidence_id": upload(case, sid, "return"),
                                          "remark": "All present."})
    assert returned.status_code == 200, returned.data
    loan.refresh_from_db()
    assert loan.status == "returned" and loan.return_evidence_id and loan.return_notes == "All present."


def test_issue_without_evidence_is_refused_and_creates_no_loan():
    case = kiosk("kiosk-noevidence")
    sid = start(case).data["session_id"]
    assert step(case, sid, "issue", {"qr_payload": case["qr"].payload}).status_code == 400
    foreign = make_issue_evidence(case["space"], eligible_member(case["space"], username="kiosk-other"))
    refused = step(case, sid, "issue", {"qr_payload": case["qr"].payload, "evidence_id": foreign.pk})
    assert refused.status_code == 400 and refused.data["code"] == "checkout_refused"
    assert not PublicToolLoan.objects.filter(makerspace=case["space"]).exists()


def test_return_needs_a_remark_and_a_photo():
    case = kiosk("kiosk-return-rules")
    sid = start(case).data["session_id"]
    step(case, sid, "issue", {"qr_payload": case["qr"].payload, "evidence_id": upload(case, sid, "issue")})
    evidence = upload(case, sid, "return")
    assert step(case, sid, "return", {"qr_payload": case["qr"].payload, "evidence_id": evidence}).status_code == 400
    assert step(case, sid, "return", {"qr_payload": case["qr"].payload, "remark": "ok"}).status_code == 400
    assert PublicToolLoan.objects.get(makerspace=case["space"]).status == "checked_out"


def test_an_ineligible_tool_cannot_be_issued_even_with_a_valid_session_and_photo():
    case = kiosk("kiosk-ineligible", public=False)
    sid = start(case).data["session_id"]
    assert step(case, sid, "scan", {"qr_payload": case["qr"].payload}).data["action"] == "ineligible"
    refused = step(case, sid, "issue", {"qr_payload": case["qr"].payload, "evidence_id": upload(case, sid, "issue")})
    assert refused.status_code == 400
    assert not PublicToolLoan.objects.filter(makerspace=case["space"]).exists()


def test_unknown_credential_is_denied_and_opens_no_session():
    case = kiosk("kiosk-denied")
    response = start(case, value="FFFFFFFF")
    assert response.data["allowed"] is False and "session_id" not in response.data


def test_the_session_is_bound_to_its_device_and_ends_on_delete_or_expiry():
    case, other = kiosk("kiosk-bound-a"), kiosk("kiosk-bound-b")
    sid = start(case).data["session_id"]
    assert step(other, sid, "scan", {"qr_payload": other["qr"].payload}).status_code == 404
    cache.delete(f"adapter-kiosk:{sid}")  # expiry
    assert step(case, sid, "scan", {"qr_payload": case["qr"].payload}).status_code == 404


def test_the_kiosk_switch_off_answers_404_before_anything_else():
    case = kiosk("kiosk-off")
    space = case["space"]
    space.enabled_features = [key for key in space.enabled_features if key != "machines.integrations.kiosk"]
    space.save(update_fields=["enabled_features"])
    assert start(case).status_code == 404
