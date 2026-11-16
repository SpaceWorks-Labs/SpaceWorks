"""Problem queues and triage retain their report, loan and exact resolution trail."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, PublicProblemReport, PublicToolLoan
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports, pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["problem-report-list", "problem-report-resolve", "problem-report-triage"])
def test_problem_route_reads_or_resolves_the_exact_seeded_report(native, name):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    request = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username, status="returned")
    loan = PublicToolLoan.objects.create(makerspace=space, request=request, requester=actor,
        target_type="direct", target_id=request.pk, target_label="Retained drill", source="admin_direct")
    report = PublicProblemReport.objects.create(makerspace=space, request=request, requester=actor,
                                                loan=loan, note="Retained loose handle")
    kwargs = {"makerspace_id": space.pk}
    if name != "problem-report-list":
        kwargs["pk"] = report.pk
    url = reverse(name, kwargs=kwargs)
    method = "GET" if name == "problem-report-list" else "POST"
    body = {"outcome": "no_issue", "note": "Inspected; handle tightened"} if name.endswith("triage") else {}

    def check(response):
        report.refresh_from_db()
        if method == "GET":
            contains(response, report.pk)
            assert response.data["results"][0]["note"] == "Retained loose handle"
            assert report.resolved_at is None
        else:
            assert (report.resolved_by_id, response.data["resolved"]) == (actor.pk, True)
            assert report.resolved_at is not None
            if name.endswith("triage"):
                assert (report.outcome, report.triage_note) == ("no_issue", body["note"])
        assert PublicProblemReport.objects.filter(makerspace=space).count() == 1
    foreign = outsider(native)
    audit = () if method == "GET" else ("problem_report.triaged",) if name.endswith("triage") else ("public_problem.resolved",)
    cycle(space, "reports", lambda: send(client, method, url, body), check,
          foreign=lambda: send(foreign, method, url, body), foreign_native=native, audit=audit)
