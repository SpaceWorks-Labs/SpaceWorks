"""PII masking is presentation only, for a superadmin without a window (owner #111 Q12)."""

from types import SimpleNamespace

import pytest
from django.core import mail
from django.test import Client
from rest_framework import serializers
from rest_framework.test import APIClient

from apps.accounts import pii_access
from apps.accounts.models import User
from apps.accounts.pii_presentation import MASK, PiiMaskingSerializerMixin
from apps.integrations.dispatch import dispatch_email
from apps.integrations.models import EmailLog
from apps.integrations.services import retry_email_log
from apps.makerspaces.models import InvitationRequest, Makerspace
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.reauth_helpers import force_recent_authenticate, force_recent_control_login

pytestmark = pytest.mark.django_db
REASON = "Checking a member complaint about contact details"


class InvitationSerializer(PiiMaskingSerializerMixin, serializers.Serializer):
    name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    status = serializers.CharField()


@pytest.fixture
def ctx():
    space = Makerspace.objects.create(name="Mask", slug="mask-space")
    other = Makerspace.objects.create(name="Mask other", slug="mask-other")
    root = User.objects.create_superuser("mask-root", email="root@mask.test", password="x" * 20)
    manager = make_staff(space, username="mask-manager")
    member = User.objects.create_user("mask-member", email="member@mask.test", first_name="Mia")
    make_membership(member, space)
    row = InvitationRequest(makerspace=space, name="Ada Lovelace", email="ada@mask.test", phone="+15550100",
                            status="pending")
    return SimpleNamespace(space=space, other=other, root=root, manager=manager, member=member, row=row)


def represent(row, viewer):
    return InvitationSerializer(row, context={"request": SimpleNamespace(user=viewer)}).data


def test_superadmin_without_a_window_sees_registry_pii_masked(ctx):
    data = represent(ctx.row, User.objects.get(pk=ctx.root.pk))
    assert data["name"] == data["email"] == data["phone"] == MASK
    assert data["status"] == "pending" and data["pii_masked"] is True
    assert ctx.row.email == "ada@mask.test"  # the model value is never touched


def test_window_unmasks_only_its_own_space(ctx):
    pii_access.open_grant(ctx.root, ctx.space, REASON)
    data = represent(ctx.row, User.objects.get(pk=ctx.root.pk))
    assert data["email"] == "ada@mask.test" and "pii_masked" not in data
    other_row = InvitationRequest(makerspace=ctx.other, name="Grace", email="g@mask.test", phone="", status="pending")
    assert represent(other_row, User.objects.get(pk=ctx.root.pk))["email"] == MASK


def test_staff_are_never_masked(ctx):
    data = represent(ctx.row, ctx.manager)
    assert data["email"] == "ada@mask.test" and "pii_masked" not in data


def control(user):
    browser = Client()
    force_recent_control_login(browser, user)
    return browser


def test_control_user_list_masks_tenant_people_but_not_platform_accounts(ctx):
    page = control(ctx.root).get("/control/accounts/user/").content.decode()
    assert "member@mask.test" not in page and MASK in page
    assert "root@mask.test" in page


def test_control_user_page_masks_until_a_per_person_reveal(ctx):
    browser = control(ctx.root)
    page = browser.get(f"/control/accounts/user/{ctx.member.pk}/change/").content.decode()
    assert "member@mask.test" not in page and "Reveal for 30 minutes" in page
    assert 'name="email"' not in page
    pii_access.open_person_grant(ctx.root, ctx.member, REASON)
    page = browser.get(f"/control/accounts/user/{ctx.member.pk}/change/").content.decode()
    assert "member@mask.test" in page


def test_control_reveal_page_needs_a_reason_and_records_it(ctx):
    browser = control(ctx.root)
    response = browser.post(f"/control/accounts/user/{ctx.member.pk}/pii-reveal/", {"reason": REASON})
    assert response.status_code == 302
    assert ctx.member.pk in set(pii_access.active_grants(ctx.root).values_list("subject_id", flat=True))


def test_workflow_mail_keeps_the_real_address_while_control_masks_it(ctx, django_capture_on_commit_callbacks):
    log = dispatch_email(to_email="person@mask.test", subject="Hello", text_body="Body", makerspace=ctx.space,
                         stream="membership", event="invitation", audience="member", sync=True)
    EmailLog.objects.filter(pk=log.pk).update(status=EmailLog.Status.FAILED)
    mail.outbox.clear()
    page = control(ctx.root).get("/control/integrations/emaillog/").content.decode()
    assert "person@mask.test" not in page
    with django_capture_on_commit_callbacks(execute=True):
        retry_email_log(ctx.root, EmailLog.objects.get(pk=log.pk))  # a superadmin-run workflow, no window open
    assert [message.to for message in mail.outbox] == [["person@mask.test"]]


def test_person_report_export_needs_a_window_for_a_superadmin(ctx):
    path = f"/api/v1/admin/platform/analytics/makerspaces/{ctx.space.pk}/reports/active-loans/export?format=csv"
    api = APIClient()
    force_recent_authenticate(api, ctx.root)
    refused = api.get(path)
    assert refused.status_code == 403 and refused.data["code"] == "pii_access_required"
    pii_access.open_grant(ctx.root, ctx.space, REASON)
    api = APIClient()
    force_recent_authenticate(api, User.objects.get(pk=ctx.root.pk))
    allowed = api.get(path)
    assert getattr(allowed, "data", None) is None or allowed.data.get("code") != "pii_access_required"


def test_space_staff_export_is_unaffected(ctx):
    path = f"/api/v1/admin/makerspace/{ctx.space.pk}/reports/active-loans/export?format=csv"
    api = APIClient()
    force_recent_authenticate(api, ctx.manager)
    response = api.get(path)
    assert getattr(response, "data", None) is None or response.data.get("code") != "pii_access_required"


def test_control_email_log_masks_space_mail_but_not_platform_mail(ctx, settings):
    """Owner decision #114: spaceless (platform) mail is unmasked; a space's mail is masked."""
    settings.PII_ENCRYPTION_ENABLED = False
    EmailLog.objects.create(makerspace=ctx.space, to_email="space-person@mask.test", subject="Space notice")
    EmailLog.objects.create(makerspace=None, to_email="platform-person@mask.test", subject="Platform notice")
    page = control(ctx.root).get("/control/integrations/emaillog/").content.decode()
    assert "platform-person@mask.test" in page
    assert "space-person@mask.test" not in page and MASK in page
