"""Pin the supported global printer-type fallback; no new dependency is needed."""

import pytest
from django.urls import reverse

from apps.machines.models import Machine, MachineServiceRequest, MachineType, ServiceQueue
from apps.machines.printer_capabilities import PRINTER_CONFIG
from apps.makerspaces.module_registry import BY_KEY
from tests.modules.family_helpers import account, client, family_space

pytestmark = pytest.mark.django_db


def test_global_printer_queue_lists_and_accepts_requests_without_machine_inventory():
    space = family_space("service-without-machines", "machine_service", "printing", "membership", "presence")
    kind, _ = MachineType.objects.get_or_create(makerspace=None, slug="3d_printer",
        defaults={"name": "3D Printer", "is_builtin": True, "capability_config": PRINTER_CONFIG})
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=kind, name="Print queue")
    assert "machines" not in BY_KEY["machine_service"].requires_modules
    assert "machines" not in space.enabled_modules
    listing = client().get(reverse("public-printer-service-queues", args=[space.slug]))
    assert listing.status_code == 200 and [row["id"] for row in listing.data] == [queue.pk]
    from tests.rbac_f6_helpers import community_member
    from tests.machines.session_helpers import check_in
    membership = community_member(space, "printer-member")
    check_in(space, membership)
    result = client(membership.user).post(reverse("public-printer-service-request", args=[space.slug]),
        {"queue_id": queue.pk, "title": "Print a bracket", "source_link": "https://example.test/bracket.stl"}, format="json")
    assert result.status_code == 201, result.data
    job = MachineServiceRequest.objects.get(makerspace=space)
    assert job.queue == queue and job.assigned_machine_id is None
    assert not Machine.objects.filter(makerspace=space).exists()
