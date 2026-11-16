"""Decision 246 (lane F8): validation conditions for the damaged-return handoff to repairs (221c)."""
import pytest

from apps.maintenance.models import IssueReport
from tests.maintenance.l16_helpers import world
from tests.maintenance.test_loan_repair_handoff import damaged_return, hand_off, quiet_storage, url  # noqa: F401
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _post(w, request, body):
    return authenticated_client(w.im).post(url(w, request), body, format="json")


def test_missing_line_id_is_a_400_and_creates_nothing():
    w = world("f8-221c-missing")
    request, _line, _ = damaged_return(w)
    assert _post(w, request, {}).status_code == 400
    assert not IssueReport.objects.filter(loan_id=request.pk).exists()


@pytest.mark.parametrize("bad", [0, -3, "abc", None, 1.5])
def test_a_non_positive_or_non_integer_line_id_is_a_400(bad):
    w = world("f8-221c-bad")
    request, _line, _ = damaged_return(w)
    assert _post(w, request, {"accountability_id": bad}).status_code == 400
    assert not IssueReport.objects.filter(loan_id=request.pk).exists()


def test_an_over_long_note_is_a_400_and_the_limit_itself_is_accepted():
    w = world("f8-221c-note")
    request, line, _ = damaged_return(w)
    assert hand_off(w.im, w, request, line, note="x" * 2001).status_code == 400
    assert not IssueReport.objects.filter(return_line=line).exists()
    assert hand_off(w.im, w, request, line, note="x" * 2000).status_code == 201


def test_a_line_of_another_loan_is_not_found_and_nothing_is_created():
    w = world("f8-221c-foreign")
    request, _line, _ = damaged_return(w)
    other_request, other_line, _ = damaged_return(w, remark="Bent leg.")
    assert _post(w, request, {"accountability_id": other_line.pk}).status_code == 404
    assert _post(w, request, {"accountability_id": 99999999}).status_code == 404
    assert not IssueReport.objects.filter(loan_id__in=[request.pk, other_request.pk]).exists()
