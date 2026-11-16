"""Open item A26 (IN7): the staff borrower history drawer (member 360 + restriction state + account-only borrowers)."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest
from tests.completeness.test_followups_248 import _member, _space
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client
from tests.test_request_workflow import make_hardware_request, make_product

pytestmark = pytest.mark.django_db


def test_member_360_reports_restriction_state():
    space = _space("a26-restricted", modules=("request_workflow",))
    target = _member(space, "a26-target")
    User.objects.filter(pk=target.pk).update(access_status=User.AccessStatus.RESTRICTED)
    viewer = staff_account(space, "a26-im", "inventory_manager")
    body = authenticated_client(viewer).get(reverse("admin-member-activity", args=[space.pk, target.pk])).json()
    assert body["access_status"] == "restricted"
    assert body["is_member"] is True


def test_account_only_borrower_is_reachable_but_a_stranger_is_404():
    space = _space("a26-account-only", modules=("request_workflow",))
    request = make_hardware_request(space, make_product(space), status=HardwareRequest.Status.ISSUED)
    viewer = staff_account(space, "a26-im-2", "inventory_manager")
    client = authenticated_client(viewer)
    body = client.get(reverse("admin-member-activity", args=[space.pk, request.requester_id])).json()
    assert body["is_member"] is False
    assert {block["area"] for block in body["areas"]} >= {"lending"}
    stranger = User.objects.create_user(username="a26-stranger", email="a26-stranger@example.test")
    assert client.get(reverse("admin-member-activity", args=[space.pk, stranger.pk])).status_code == 404


def test_a_borrower_of_another_space_is_404():
    space = _space("a26-home", modules=("request_workflow",))
    other = _space("a26-other", modules=("request_workflow",))
    request = make_hardware_request(other, make_product(other))
    viewer = staff_account(space, "a26-im-3", "inventory_manager")
    response = authenticated_client(viewer).get(reverse("admin-member-activity", args=[space.pk, request.requester_id]))
    assert response.status_code == 404


def test_handout_only_desk_is_still_refused():
    space = _space("a26-desk", modules=("request_workflow",))
    request = make_hardware_request(space, make_product(space))
    plain = staff_account(space, "a26-plain", "member")
    response = authenticated_client(plain).get(reverse("admin-member-activity", args=[space.pk, request.requester_id]))
    assert response.status_code == 404


def test_staff_request_payload_carries_the_requester_id():
    from apps.hardware_requests.serializers import AdminRequestSerializer

    field = AdminRequestSerializer().fields["requester_id"]
    assert field.read_only and field.source == "requester_id"
