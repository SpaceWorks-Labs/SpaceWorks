"""MOD-1: /qr/boxes and its /qr/containers alias are the same operation; conditions on QR box creation."""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.boxes.models import Box, QrCode
from tests.return_helpers import authenticated_client, make_box, make_member, make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("route", ["boxes", "containers"])
def test_box_and_container_routes_create_one_box_one_active_qr_and_one_audit_row(route):
    space = make_space(f"m1-qr-{route}")
    admin = make_member(f"m1-qr-{route}-admin", space)
    response = authenticated_client(admin).post(
        f"/api/v1/admin/qr/{route}", {"makerspace_id": space.id, "label": "Bac à pièces ⚙ <b>1</b>"}, format="json")
    assert response.status_code == 201
    box = Box.objects.get(makerspace=space)
    assert box.label == "Bac à pièces ⚙ <b>1</b>"
    qr = QrCode.objects.get(makerspace=space, target_type=QrCode.TargetType.BOX)
    assert (qr.target_id, qr.payload, qr.status) == (box.id, box.code, QrCode.Status.ACTIVE)
    assert AuditLog.objects.filter(makerspace=space, target_id=str(box.pk)).count() >= 1


@pytest.mark.parametrize("route", ["boxes", "containers"])
def test_box_creation_rejects_blank_label_foreign_parent_and_other_tenants(route):
    space, other = make_space(f"m1-qr-bad-{route}"), make_space(f"m1-qr-bad-o-{route}")
    admin = make_member(f"m1-qr-bad-admin-{route}", space)
    client = authenticated_client(admin)
    url = f"/api/v1/admin/qr/{route}"
    assert client.post(url, {"makerspace_id": space.id, "label": ""}, format="json").status_code == 400
    foreign_parent = make_box(other, "Theirs")
    assert client.post(url, {"makerspace_id": space.id, "label": "x", "parent_id": foreign_parent.id},
                       format="json").status_code == 404
    assert client.post(url, {"makerspace_id": other.id, "label": "x"}, format="json").status_code in (403, 404)
    assert APIClient().post(url, {"makerspace_id": space.id, "label": "x"}, format="json").status_code in (401, 403)
    requester = authenticated_client(make_user(f"m1-qr-req-{route}"))
    assert requester.post(url, {"makerspace_id": space.id, "label": "x"}, format="json").status_code in (403, 404)
    assert not Box.objects.filter(makerspace=space).exists() and not QrCode.objects.filter(makerspace=space).exists()
