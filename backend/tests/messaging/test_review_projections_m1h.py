"""Reviewed addressed projections on the canonical envelope seam (D1).

Domain adapters project only allow-listed scalars into envelope context through
``addressed_context``; approved WhatsApp templates bind those values positionally.
Payment payer/staff projections are covered end to end on real ledger envelopes by
``tests/payments/test_recon_fr_payment_context.py``.
"""
import builtins
from unittest.mock import patch

import pytest

from apps.hardware_requests.notification_projection import addressed_context
from apps.integrations.email_templates import printing_context
from apps.integrations.models_endpoints import ChannelConfiguration, WhatsAppTemplate
from apps.integrations.notification_wa_meta_templates import template_content
from apps.machines.models import MachineServiceRequest, MachineType, ServiceQueue
from apps.machines.service_printing_projection import printing_projection

pytestmark = pytest.mark.django_db


def project(space, row, audience):
    # Core projection never imports optional inbox/printing-email adapters.
    original_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name.startswith("apps.notifications") or name in {
            "apps.payments.notifications", "apps.machines.service_printing_emails",
            "apps.integrations.notifications_research",
        }:
            raise AssertionError("Addressed projections imported optional inbox adapters")
        return original_import(name, *args, **kwargs)

    staff_context = printing_context(printing_projection(row), "", "")
    with patch("builtins.__import__", side_effect=guard):
        return addressed_context(space, "printing", "started", audience, staff_context)


def test_printing_parameters_use_kernel_adapter_quantity_and_status(space, member):
    machine_type = MachineType.objects.create(makerspace=space, slug="projection-printer", name="Projection printer")
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=machine_type, name="Projection queue")
    request = MachineServiceRequest.objects.create(makerspace=space, queue=queue, requester=member,
        status="in_progress", title="PRIVATE TITLE", reason="PRIVATE REASON", contact_email="private@example.test",
        capability_payload={"quantity": 7, "project_brief": "PRIVATE BRIEF"})
    own, staff = project(space, request, "requester"), project(space, request, "staff")
    expected = {"makerspace.name": space.name, "print_request.id": request.pk,
                "print_request.status": "printing", "print_request.quantity": 7}
    assert own == staff == expected
    assert "PRIVATE" not in str(own) and "private@" not in str(own)
    config = ChannelConfiguration.objects.create(makerspace=space, channel="whatsapp", provider="meta")
    binding = WhatsAppTemplate.objects.create(configuration=config, event="started", audience="member",
        locale="en", template_name="reviewed_parameters", approved=True, needs_review=False,
        variables=["print_request.quantity", "print_request.status"])
    content = template_content(binding, own)
    assert [item["text"] for item in content["template"]["components"][0]["parameters"]] == ["7", "printing"]
