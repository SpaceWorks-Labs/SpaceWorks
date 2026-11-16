"""Bootstrap ownership is atomic for new spaces and conservative on reruns."""
from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.organizations.services_owner import bootstrap_owner_organization
from tests.organizations.test_admin_create_link import superadmin
from tests.organizations.test_org_authority import make_makerspace
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db


def setup(*, organization_name=None):
    stdout, stderr = StringIO(), StringIO()
    options = {} if organization_name is None else {"organization_name": organization_name}
    call_command(
        "setup_instance", username="org-setup-super", password="owner-test-password",
        email="owner@example.test", makerspace_name="Bootstrap Lab",
        makerspace_slug="bootstrap-lab", profile="minimal", stdout=stdout, stderr=stderr,
        **options,
    )
    return stdout.getvalue(), stderr.getvalue()


@pytest.fixture(autouse=True)
def no_environment_owner_default(monkeypatch):
    monkeypatch.delenv("SETUP_ORGANIZATION_NAME", raising=False)


@pytest.mark.parametrize("name,expected", [(None, "Bootstrap Lab"), ("Community Network", "Community Network")])
def test_setup_creates_named_or_default_owner(name, expected):
    stdout, stderr = setup(organization_name=name)
    row = OrganizationMakerspace.objects.get(makerspace__slug="bootstrap-lab")
    assert row.relationship == "owner" and row.organization.name == expected
    assert row.organization.created_by == row.makerspace.created_by == row.created_by
    assert f"Owner organization: {expected} (owns Bootstrap Lab)." in stdout
    assert not stderr


def test_setup_rerun_keeps_owner_without_creating_a_second_organization():
    setup(organization_name="Original Owner")
    original = OrganizationMakerspace.objects.get()
    setup(organization_name="Ignored Replacement")
    assert OrganizationMakerspace.objects.get() == original
    assert list(Organization.objects.values_list("name", flat=True)) == ["Original Owner"]
    assert AuditLog.objects.filter(action="organization.created").count() == 1


def test_ownerless_existing_space_gets_an_owner_on_rerun():
    space = make_makerspace("bootstrap-lab")
    setup(organization_name="Backfilled Owner")
    row = OrganizationMakerspace.objects.get(makerspace=space)
    assert row.relationship == "owner" and row.organization.name == "Backfilled Owner"
    assert Makerspace.objects.count() == 1


def test_new_space_owner_failure_rolls_back_space_organization_link_and_audits(monkeypatch):
    def fail_after_assignment(*args, **kwargs):
        bootstrap_owner_organization(*args, **kwargs)
        raise ValidationError("Forced owner assignment failure")

    monkeypatch.setattr(
        "apps.makerspaces.management.commands.setup_instance.bootstrap_owner_organization",
        fail_after_assignment,
    )
    with pytest.raises(ValidationError, match="Forced owner assignment failure"):
        setup(organization_name="Rolled Back")
    assert not Makerspace.objects.exists()
    assert not Organization.objects.exists() and not OrganizationMakerspace.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="organization.").exists()


@pytest.mark.django_db(transaction=True)
def test_ownerless_frozen_existing_space_warns_and_setup_succeeds():
    actor = superadmin()
    space = make_makerspace("bootstrap-lab")
    close_gate(space, actor)
    stdout, stderr = setup(organization_name="Skipped Owner")
    assert "found makerspace bootstrap-lab" in stdout
    assert "Skipped assigning an owner organization:" in stderr
    assert not Organization.objects.exists() and not OrganizationMakerspace.objects.exists()
    assert Makerspace.objects.get(pk=space.pk).slug == "bootstrap-lab"


def test_generated_password_bootstrap_still_assigns_owner(monkeypatch):
    # A generated first-run password sets must_change_password; the API guard that
    # rejects such users must not stop the trusted CLI bootstrap from completing.
    monkeypatch.delenv("SETUP_SUPERADMIN_PASSWORD", raising=False)
    stdout, stderr = StringIO(), StringIO()
    call_command(
        "setup_instance", username="generated-super", email="gen@example.test",
        makerspace_name="Generated Lab", makerspace_slug="generated-lab", profile="minimal",
        stdout=stdout, stderr=stderr,
    )
    row = OrganizationMakerspace.objects.get(makerspace__slug="generated-lab")
    assert row.relationship == "owner" and row.organization.name == "Generated Lab"
    assert row.created_by.must_change_password is True
    assert "Generated superadmin password:" in stderr.getvalue() + stdout.getvalue()
    assert "Owner organization: Generated Lab (owns Generated Lab)." in stdout.getvalue()
