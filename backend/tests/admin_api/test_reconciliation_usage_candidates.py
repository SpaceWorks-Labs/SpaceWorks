import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.machines.models import Machine, MachineType
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.module_install import install_module
from tests.accounts.account_factories import make_membership, make_staff

pytestmark = pytest.mark.django_db


def test_usage_picker_excludes_staff_revoked_and_foreign_memberships():
    space = Makerspace.objects.create(name="Usage", slug="recon-picker")
    other = Makerspace.objects.create(name="Other", slug="recon-picker-other")
    install_module(space, "machines")
    kind = MachineType.objects.create(makerspace=space, name="Usage type", slug="recon-picker-type")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Usage machine")
    member = User.objects.create_user(username="recon-picker-member", email="same@example.test")
    staff = make_staff(space, username="recon-picker-staff", email="same@example.test")
    revoked = User.objects.create_user(username="recon-picker-revoked")
    foreign = User.objects.create_user(username="recon-picker-foreign")
    make_membership(member, space)
    make_membership(revoked, space, status="revoked")
    make_membership(foreign, other)
    actor = User.objects.create_superuser(username="recon-picker-platform")
    client = APIClient()
    client.force_authenticate(actor)
    response = client.get(reverse("admin-machine-usage-candidates", kwargs={"pk": machine.pk}))
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert [row["user_id"] for row in response.data["results"]] == [member.pk]
