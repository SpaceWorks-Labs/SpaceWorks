"""Every visible archive/purge confirmation includes advisory owned/routed money."""
import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces import lifecycle
from apps.makerspaces.models import Makerspace, MakerspaceArchiveRequest
from apps.payments.models import Payment
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.billing_docs.test_r1_bills import pending
from tests.payments.test_refunds import paid_deposit

pytestmark = pytest.mark.django_db


def confirmation_fixture():
    actor = User.objects.create_superuser("s4b-impact-owner", email="private-owner@example.test")
    space, member, _owned = pending("s4b-impact-visible")
    host = Makerspace.objects.create(name="Remote host", slug="s4b-impact-host")
    routed = paid_deposit(host, member, status="pending", intent="pi-s4b-routed")
    Payment.objects.filter(pk=routed.pk).update(via_makerspace=space)
    request = MakerspaceArchiveRequest.objects.create(makerspace=space, requested_by=member, reason="Visible archive reason")
    client = Client()
    force_recent_control_login(client, actor)
    return client, actor, space, request


@pytest.mark.parametrize("action", ["archive_makerspaces", "purge_makerspaces", "approve_selected"])
def test_existing_confirmation_paths_include_real_impact(action):
    client, _, space, archive_request = confirmation_fixture()
    if action == "purge_makerspaces":
        space.archived_at = timezone.now()
        space.save(update_fields=["archived_at"])
    model = "makerspacearchiverequest" if action == "approve_selected" else "makerspace"
    selected = archive_request if action == "approve_selected" else space
    response = client.post(reverse(f"admin:makerspaces_{model}_changelist"), {
        "action": action, ACTION_CHECKBOX_NAME: [str(selected.pk)],
    })
    assert response.status_code == 200
    key = {"archive_makerspaces": "makerspaces", "purge_makerspaces": "impacts", "approve_selected": "requests"}[action]
    row = response.context_data[key][0]
    assert (row["owned_pending"], row["routed_pending"], row["total_pending"]) == (1, 1, 2)
    body = response.content.decode().lower()
    assert "owned pending" in body and "routed pending" in body


def test_ordinary_delete_confirmation_warns_about_money():
    client, _, space, _ = confirmation_fixture()
    space.archived_at = timezone.now()
    space.save(update_fields=["archived_at"])
    response = client.get(reverse("admin:makerspaces_makerspace_delete", args=[space.pk]))
    assert response.status_code == 200
    assert "1 owned pending, 1 routed pending, 2 total pending" in response.content.decode()


