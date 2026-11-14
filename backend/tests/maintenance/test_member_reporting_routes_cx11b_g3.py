"""Owner-only reports (#103); personal collection and authentication keep 494's exceptions."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from rest_framework.test import APIClient

from apps.maintenance.models import IssueReport
from tests.maintenance.report_world_cx11b_g3 import SOURCES, report_world
from tests.maintenance.route_support_cx11b_g3 import foreign_client, person_client, prove, send
from tests.return_helpers import make_member
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]
CASES = [(source, key, native) for source, (_, feature, parent) in SOURCES.items()
         for key in dict.fromkeys((feature, parent, *(["machines"] if source == "session" else [])))
         for native in (False, True)]


@pytest.mark.parametrize("source,key,native", CASES)
def test_member_report_effect_eligibility_and_independent_dependencies(source, key, native):
    w = report_world(source, native)
    outsider = foreign_client(native, personal=True)
    second = person_client(make_member("g3-second-reporter", w.space, membership_role="member", role="requester"),
                           w.space, native)
    field = "enabled_features" if "." in key else "enabled_modules"

    def contract():
        # #103: source eligibility is a 403 for a non-owner; reporting's global
        # surface gate precedes it. Session-policy off is itself ineligibility.
        if key not in getattr(w.space, field) and key != "machines.sessions":
            return 404, "capability_disabled"
        return 403, "reporter_not_eligible"

    def check(response):
        row = IssueReport.objects.get(pk=response.data["id"])
        assert (row.reporter_id, row.title, row.description, row.state, row.subject_type) == (
            w.person.pk, "Loose handle", "Handle wobbles", "reported", w.kind)
        assert getattr(row, w.origin_field + "_id") == w.origin.pk
        assert IssueReport.objects.filter(reporter=w.person).count() == 1
        assert row.events.get().kind == "reported"

    prove(w.space, {"origin": w.origin}, key,
          lambda c: send(c or w.client, "member-issues", [], "post", w.body), check, status=201,
          off=(403, "reporter_not_eligible") if key == "machines.sessions" else (404, "capability_disabled"),
          outsiders=[(outsider, contract), (second, contract)], audits={"issue.reported": 1})


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.issue_reporting", "loans.enabled"])
def test_member_loan_items_restores_exact_owned_item(key, native):
    w = report_world("loan", native)
    outsider = foreign_client(native, personal=True)
    expected = [{"product_id": w.product.pk, "asset_id": None, "name": w.product.name}]

    def check(response):
        assert response.data == expected

    def contract():
        return (403, "reporter_not_eligible") if key in w.space.enabled_features else (404, "capability_disabled")

    prove(w.space, {"loan": w.origin, "product": w.product}, key,
          lambda c: send(c or w.client, "member-issue-loan-items", [], body={"makerspace": w.space.pk, "loan": w.origin.pk}),
          check, off=(404, "capability_disabled"), outsiders=[(outsider, contract)])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("source", ["loan", "booking", "job"])
@pytest.mark.parametrize("gate", ["feature", "parent"])
def test_member_history_is_hidden_off_and_restored_for_its_owner(source, gate, native):
    # Regression: folded switch C-8/C-9 says off means no read surface. Current
    # MemberIssueListView.get has no area filter. Like work-order collections,
    # a global personal list must hide this stream without hiding other spaces.
    w = report_world(source, native)
    area, feature, parent = SOURCES[source]
    from apps.maintenance.repairs import services_issues as svc
    row = svc.file_report(w.space, reporter=w.person, source=w.origin_field, origin=w.origin,
        subject_type=w.kind, subject=w.subject, title="Retained personal report", description="Private", validated=[])
    key = feature if gate == "feature" else parent
    other = foreign_client(native, personal=True)
    second = person_client(make_member("g3-second-history", w.space, membership_role="member", role="requester"),
                           w.space, native)
    with no_domain_writes():
        answer = send(other, "member-issues", [])
    assert response_pair(answer) == (200, None) and answer.data == []

    def check(response):
        assert [(r["id"], r["title"]) for r in response.data] == [(row.pk, "Retained personal report")]
        assert "description" not in response.data[0] and "reporter_email" not in response.data[0]

    def hidden(response):
        assert response.data == []

    def call(c):
        response = send(c or w.client, "member-issues", [])
        if c is not None:
            assert response.data == []
        return response

    prove(w.space, {"issue": row}, key, call, check,
          off=(200, None), off_check=hidden, outsiders=[(other, (200, None)), (second, (200, None))])
    with no_domain_writes():
        answer = send(other, "member-issues", [])
    assert response_pair(answer) == (200, None) and answer.data == []


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("source", ["loan", "booking", "job"])
@pytest.mark.parametrize("gate", ["feature", "parent"])
def test_member_photo_presign_is_bound_to_account_and_space(source, gate, native, monkeypatch):
    from django.core import signing
    from apps.maintenance.repairs import photos, storage
    w = report_world(source, native)
    _, feature, parent = SOURCES[source]
    key = feature if gate == "feature" else parent
    uploads = []

    def presign(object_key, content_type):
        uploads.append((object_key, content_type))
        return {"url": "https://storage.example.test/" + storage.staging_key(object_key), "method": "PUT"}
    monkeypatch.setattr(storage, "presign", presign)

    def check(response):
        grant = signing.loads(response.data["photo_token"], salt=photos.SALT, max_age=photos.MAX_AGE)
        assert (grant["m"], grant["o"]) == (w.space.pk, photos.owner_for_user(w.person))
        assert storage.owns_key(grant["k"], w.space.pk)
        assert uploads[-1] == (grant["k"], "image/jpeg")
        assert response.data["upload"]["url"].endswith(storage.staging_key(grant["k"]))
        assert not IssueReport.objects.filter(makerspace=w.space).exists()

    prove(w.space, {"origin": w.origin}, key,
          lambda c: send(c or w.client, "member-issue-photo-upload", [], "post",
                         {"makerspace_id": w.space.pk, "content_type": "image/jpeg"}), check, status=201,
          off=(404, "capability_disabled"), outsiders=[(APIClient(), (401, "not_authenticated"))])

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
