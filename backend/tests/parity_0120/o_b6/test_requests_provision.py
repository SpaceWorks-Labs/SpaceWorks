"""Decision 295: ask for an organization workspace, approve it into org + space atomically, or decline."""
import pytest
from django.core import mail

from apps.accounts.models import StaffInvitation
from apps.hosting_requests import provision, workflow
from apps.hosting_requests.models import HostingRequest
from apps.makerspaces.models import Makerspace
from apps.makerspaces.setup_areas import active_areas
from apps.organizations.models import Organization, OrganizationInvitation, OrganizationMakerspace
from tests.hosting_requests.helpers import SUBMIT, anonymous, payload, public_row, superadmin

pytestmark = pytest.mark.django_db


def org_payload(**overrides):
    return payload(requested_kind="organization", location="", new_organization_name="", **overrides)


@pytest.mark.usefixtures("managed")
def test_public_form_accepts_an_organization_request_without_a_location():
    response = anonymous().post(SUBMIT, org_payload(), format="json")
    assert response.status_code == 202
    row = HostingRequest.objects.get()
    assert row.requested_kind == "organization" and row.location == ""


@pytest.mark.usefixtures("managed")
def test_a_makerspace_request_still_needs_a_location():
    response = anonymous().post(SUBMIT, payload(location=""), format="json")
    assert response.status_code == 400 and "location" in response.data


@pytest.mark.usefixtures("managed")
def test_request_kind_must_be_known():
    assert anonymous().post(SUBMIT, org_payload(requested_kind="nonsense"), format="json").status_code == 400


@pytest.mark.usefixtures("managed")
def test_approve_creates_org_and_space_atomically_and_notifies(django_capture_on_commit_callbacks):
    root = superadmin()
    row, _ = public_row(requested_kind="organization", space_name="Chess Club", proposed_slug="chess",
                        location="", new_organization_name="Chess Club Inc")
    with django_capture_on_commit_callbacks(execute=True):
        row, space = provision.approve_and_create(root, row.pk)
    assert row.status == "accepted" and row.created_makerspace_id == space.pk
    assert space.kind == "organization" and space.slug == "chess"
    assert active_areas(space)["events"] and not active_areas(space)["machines"]
    link = OrganizationMakerspace.objects.get(makerspace=space)
    assert link.relationship == "owner" and link.organization.name == "Chess Club Inc"
    assert link.organization.review_status == "approved"
    assert OrganizationInvitation.objects.filter(organization=link.organization).exists()
    assert StaffInvitation.objects.filter(makerspace=space).exists()
    assert any("workspace is ready" in message.subject for message in mail.outbox)


@pytest.mark.usefixtures("managed")
def test_a_failure_rolls_everything_back(monkeypatch):
    root = superadmin("rollback-root")
    row, _ = public_row(requested_kind="organization", space_name="Doomed", proposed_slug="doomed",
                        new_organization_name="Doomed Org")

    def boom(*args, **kwargs):
        raise RuntimeError("delivery failed")

    monkeypatch.setattr(provision, "_invite_governor", boom)
    with pytest.raises(RuntimeError):
        provision.approve_and_create(root, row.pk)
    row.refresh_from_db()
    assert row.status == "submitted" and row.created_makerspace_id is None
    assert not Makerspace.objects.filter(slug="doomed").exists() and not Organization.objects.exists()


@pytest.mark.usefixtures("managed")
def test_only_a_superadmin_may_approve():
    from apps.accounts.models import User
    row, _ = public_row()
    plain = User.objects.create_user(username="plain-user", email="p@example.test")
    with pytest.raises(Exception):
        provision.approve_and_create(plain, row.pk)
    assert not Makerspace.objects.exists()


@pytest.mark.usefixtures("managed")
def test_a_makerspace_request_keeps_the_makerspace_kind():
    root = superadmin("mk-root")
    row, _ = public_row(space_name="Riverside", proposed_slug="riverside", new_organization_name="Riverside Co")
    _, space = provision.approve_and_create(root, row.pk)
    assert space.kind == "makerspace"


@pytest.mark.usefixtures("managed")
def test_second_approval_is_a_conflict():
    root = superadmin("twice-root")
    row, _ = public_row(space_name="Once", proposed_slug="once")
    provision.approve_and_create(root, row.pk)
    with pytest.raises(Exception):
        provision.approve_and_create(root, row.pk)
    assert Makerspace.objects.filter(slug__startswith="once").count() == 1


@pytest.mark.usefixtures("managed")
def test_decline_stores_the_reason_creates_nothing_and_mails_with_the_noun(django_capture_on_commit_callbacks):
    root = superadmin("decline-root")
    row, _ = public_row(requested_kind="organization", space_name="Nope Club")
    with django_capture_on_commit_callbacks(execute=True):
        workflow.reject(root, row.pk, "Not a fit for this platform, sorry.")
    row.refresh_from_db()
    assert row.status == "rejected" and row.created_makerspace_id is None
    assert not Makerspace.objects.exists() and not Organization.objects.exists()
    assert "organization Nope Club" in mail.outbox[-1].body


@pytest.mark.usefixtures("self_host")
def test_request_form_is_off_by_default_on_self_host_and_404s():
    assert anonymous().post(SUBMIT, org_payload(), format="json").status_code == 404
    assert "hosting_requests" not in anonymous().get("/api/v1/config").data


@pytest.mark.usefixtures("self_host")
def test_operator_switch_opens_the_form_on_self_host(settings):
    settings.PUBLIC_SPACE_REQUESTS_ENABLED = True
    assert anonymous().post(SUBMIT, org_payload(), format="json").status_code == 202
    config = anonymous().get("/api/v1/config").data
    assert config["hosting_requests"] == {"enabled": True, "kinds": ["makerspace", "organization"]}
