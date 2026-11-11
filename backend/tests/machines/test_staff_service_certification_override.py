"""MP-96: staff-entered machine-service jobs accept an audited certification override."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.machines.models import Machine, MachineServiceRequest
from tests.machines.certification_helpers import _certification, _machine_type, _manager, _member, _space

pytestmark = pytest.mark.django_db


def _world(slug):
    space = _space(slug)
    kind = _machine_type(space)
    _certification(space, kind)
    manager, _ = _manager(space, slug + "-manager", kind)
    member, _ = _member(space, slug + "-member")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser")
    api = APIClient()
    api.force_authenticate(manager)
    path = reverse("admin-machine-service-request-list-create", args=[space.pk])
    return space, manager, member, machine, api, path


def test_staff_submit_for_an_uncertified_member_needs_an_override_reason():
    space, manager, member, machine, api, path = _world("mp96-gate")
    body = {"requester_id": member.pk, "machine_id": machine.pk, "title": "Cut panels"}

    refused = api.post(path, body, format="json")
    assert refused.status_code == 403
    assert not MachineServiceRequest.objects.filter(makerspace=space).exists()

    accepted = api.post(path, {**body, "certification_override_reason": "Trained on site today"}, format="json")
    assert accepted.status_code == 201, accepted.content
    entry = AuditLog.objects.get(action="certification.override", makerspace=space)
    assert entry.actor == manager
    assert entry.meta["reason"] == "Trained on site today"
    assert "certification_override_reason" not in accepted.json()


def test_override_from_staff_without_authority_over_the_type_is_refused():
    space, _, member, machine, _, path = _world("mp96-scope")
    other_kind = _machine_type(space, label="Lathe")
    outsider, _ = _manager(space, "mp96-scope-outsider", other_kind)
    api = APIClient()
    api.force_authenticate(outsider)
    body = {"requester_id": member.pk, "machine_id": machine.pk, "title": "Cut", "certification_override_reason": "Trust me"}
    response = api.post(path, body, format="json")
    # The outsider cannot reach a machine outside their type scope at all, or is refused by the gate.
    assert response.status_code in (403, 404)
    assert not AuditLog.objects.filter(action="certification.override", makerspace=space).exists()
