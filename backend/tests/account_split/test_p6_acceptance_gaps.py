"""Acceptance seams left after P1-P5: operator bootstrap and module-off onboarding."""

from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import PlatformLoginMethods, StaffInvitation, User
from apps.audit.models import AuditLog
from apps.backup.models import DeploymentRecoveryState
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.tenant_restore_superadmin import create_target_superadmin
from .p1_helpers import staff
from .p3_helpers import PASSWORD, base, client, context

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skip(reason="U-A1/U-B: same-e-mail member/staff/platform accounts violate uniq_person_email and the staff-account HTTP onboarding (set-password route, staff login context and cookie) is retired; the premise of this module is retired"),
]
ORIGIN = "http://localhost:5000"
NEW_PASSWORD = "Fresh separate account password 638!"


def assert_platform(user):
    assert user.account_kind == "platform"
    assert user.is_superuser and user.is_staff and user.role == User.Role.SUPERADMIN
    assert user.is_active and user.access_status == User.AccessStatus.ACTIVE
    assert user.staff_makerspace_id is None and user.retired_at is None
    assert not user.makerspace_memberships.exists()


@pytest.mark.parametrize("installer_environment", [False, True])
def test_setup_and_installer_environment_create_separate_platform_operator(monkeypatch, installer_environment):
    email = "bootstrap@example.test"
    member = User.objects.create_user("bootstrap-member", email=email, password=PASSWORD)
    space = Makerspace.objects.create(name="Existing", slug="bootstrap-existing")
    employee, _ = staff(space, "bootstrap-staff", email=email, password=PASSWORD)
    for key in ("SETUP_SUPERADMIN_USERNAME", "SETUP_SUPERADMIN_PASSWORD", "SETUP_MODULE_PROFILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SETUP_MFA_ENABLED", "n")
    monkeypatch.setenv("SETUP_SOCIAL_PROVIDERS", "none")
    options = {"organization_name": "Bootstrap operator"}
    if installer_environment:
        # setup-host-orchestration.sh passes these environment variables to setup_instance.
        for key, value in {
            "SETUP_SUPERADMIN_USERNAME": "bootstrap-platform",
            "SETUP_SUPERADMIN_EMAIL": email,
            "SETUP_SUPERADMIN_PASSWORD": NEW_PASSWORD,
            "SETUP_MAKERSPACE_NAME": "Bootstrap",
            "SETUP_MAKERSPACE_SLUG": "bootstrap",
        }.items():
            monkeypatch.setenv(key, value)
    else:
        options.update(username="bootstrap-platform", email=email, password=NEW_PASSWORD,
                       makerspace_name="Bootstrap", makerspace_slug="bootstrap")
    call_command("setup_instance", stdout=StringIO(), **options)
    operator = User.objects.get(username="bootstrap-platform")
    assert_platform(operator)
    assert operator.check_password(NEW_PASSWORD)
    call_command("setup_instance", stdout=StringIO(), **options)
    assert User.objects.filter(account_kind="platform").count() == 1
    assert Makerspace.objects.get(slug="bootstrap").created_by_id == operator.pk
    for account, kind in ((member, "member"), (employee, "staff")):
        account.refresh_from_db()
        assert account.account_kind == kind and account.check_password(PASSWORD)


def test_target_restore_creates_platform_without_adopting_same_email_staff_or_member():
    email = "restore-operator@example.test"
    member = User.objects.create_user("restore-member", email=email, password=PASSWORD)
    space = Makerspace.objects.create(name="Existing", slug="restore-existing")
    employee, _ = staff(space, "restore-staff", email=email, password=PASSWORD)
    DeploymentRecoveryState.objects.update_or_create(
        pk=1, defaults={"mode": DeploymentRecoveryState.Mode.TARGET_IMPORT},
    )
    options = dict(email=email, run_id=uuid4(), artifact_sha256="a" * 64,
                   delivery_store=SimpleNamespace(get_or_prepare=lambda **_: {"secret": NEW_PASSWORD}))
    operator = create_target_superadmin(**options)
    assert_platform(operator)
    assert operator.pk not in {member.pk, employee.pk}
    assert operator.must_change_password and operator.check_password(NEW_PASSWORD)
    assert create_target_superadmin(**options).pk == operator.pk
    assert DeploymentRecoveryState.load().recovery_principal_id == operator.pk
    event = AuditLog.objects.get(action="tenant_migration.target_superadmin_created")
    assert event.actor_id == operator.pk and NEW_PASSWORD not in str(event.meta)
    for account, kind in ((member, "member"), (employee, "staff")):
        account.refresh_from_db()
        assert account.account_kind == kind and account.check_password(PASSWORD)


def test_host_recovery_reuses_only_existing_platform_never_promotes_shared_email_accounts():
    email = "recovery-operator@example.test"
    member = User.objects.create_user("recovery-member", email=email, password=PASSWORD)
    space = Makerspace.objects.create(name="Recovery", slug="recovery")
    employee, _ = staff(space, "recovery-staff", email=email, password=PASSWORD)
    operator = User.objects.create_superuser("recovery-platform", email=email, password=PASSWORD)
    DeploymentRecoveryState.objects.update_or_create(
        pk=1, defaults={"mode": DeploymentRecoveryState.Mode.QUARANTINED},
    )
    for account in (member, employee):
        with pytest.raises(CommandError, match="already be a superadmin"):
            call_command("recover_superadmin", account.username, password=NEW_PASSWORD, stdout=StringIO())
        account.refresh_from_db()
        assert account.check_password(PASSWORD) and not account.is_superuser
    output = StringIO()
    call_command("recover_superadmin", operator.username, password=NEW_PASSWORD, stdout=output)
    operator.refresh_from_db()
    assert_platform(operator)
    assert operator.check_password(NEW_PASSWORD) and not operator.must_change_password
    state = DeploymentRecoveryState.load()
    assert state.recovery_principal_id == operator.pk
    assert state.mode == DeploymentRecoveryState.Mode.QUARANTINED
    assert User.objects.count() == 3
    event = AuditLog.objects.get(action="backup.recovery_superadmin_established")
    assert event.actor_id == operator.pk and NEW_PASSWORD not in str(event.meta)


@pytest.mark.parametrize("identity", ["email", "username"])
def test_staff_http_onboarding_and_first_password_change_with_optional_modules_off(settings, identity):
    ctx = context(settings)
    # No tenant can keep deployment-level member accounts available accidentally.
    for space in (ctx.space, ctx.other):
        space.enabled_modules = [key for key in space.enabled_modules
                                 if key not in {"email", "membership", "member_accounts"}]
        space.enabled_features = [key for key in space.enabled_features
                                  if key not in {"staff.invitations", "security.staff_mfa_required"}]
        space.save(update_fields=["enabled_modules", "enabled_features"])
    PlatformLoginMethods.objects.update_or_create(
        pk=1, defaults={"mfa_enabled": False, "password_enabled": False},
    )
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    api = client(ctx.manager)
    policy = api.get(base(ctx.space) + "policy")
    assert policy.status_code == 200 and not policy.data["email_onboarding_available"]
    created = api.post(base(ctx.space), {
        "display_name": "Offline onboarded", identity: "onboard@example.test" if identity == "email" else "onboard",
        "roles": ["handover"], "machine_type_ids": [],
    }, format="json")
    assert created.status_code == 201, created.data
    account = User.objects.get(pk=created.data["account"]["id"])
    assert not created.data["invitation_sent"] and not StaffInvitation.objects.filter(account=account).exists()
    assert account.account_kind == "staff" and account.staff_makerspace_id == ctx.space.pk
    assert not account.has_usable_password() and account.must_change_password
    issued = api.post(f"{base(ctx.space)}{account.pk}/set-password/", {"password": PASSWORD}, format="json")
    assert issued.status_code == 200 and issued.data == {"generated_password": None}
    assert "no-store" in issued["Cache-Control"]
    browser = APIClient()
    login_body = {"username": getattr(account, identity), "password": PASSWORD,
                  "context": "staff", "makerspace": ctx.space.slug}
    signed_in = browser.post("/api/v1/auth/login", login_body, format="json", HTTP_ORIGIN=ORIGIN)
    assert signed_in.status_code == 200, signed_in.data
    assert signed_in.data["user"]["id"] == account.pk and signed_in.data["user"]["must_change_password"]
    claims = AccessToken(signed_in.data["access"])
    assert claims["kind"] == "staff" and claims["makerspace"] == ctx.space.pk
    assert f"refresh_token_staff_{ctx.space.slug}" in signed_in.cookies
    browser.credentials(HTTP_AUTHORIZATION=f"Bearer {signed_in.data['access']}")
    changed = browser.post("/api/v1/auth/change-password", {
        "current_password": PASSWORD, "new_password": NEW_PASSWORD,
    }, format="json", HTTP_ORIGIN=ORIGIN)
    assert changed.status_code == 200, changed.data
    account.refresh_from_db()
    assert account.check_password(NEW_PASSWORD) and not account.must_change_password
    assert account.credential_generation == 2
    assert AuditLog.objects.filter(action="staff.account_created", target_id=str(account.pk)).exists()
    reset = AuditLog.objects.get(action="staff_account.password_reset", target_id=str(account.pk))
    assert PASSWORD not in str(reset.meta)
    assert AuditLog.objects.filter(action="user.password_changed", actor=account).exists()
    browser.credentials()
    login_body["password"] = NEW_PASSWORD
    again = browser.post("/api/v1/auth/login", login_body, format="json", HTTP_ORIGIN=ORIGIN)
    assert again.status_code == 200 and not again.data["user"]["must_change_password"]


def test_http_member_signup_with_staff_email_keeps_credentials_and_verification_separate(settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    email = "signup-shared@example.test"
    space = Makerspace.objects.create(name="Signup", slug="signup")
    if "member_accounts" not in space.enabled_modules:
        space.enabled_modules = [*space.enabled_modules, "member_accounts"]
        space.save(update_fields=["enabled_modules"])
    employee, _ = staff(space, "signup-staff", email=email, password=PASSWORD)
    delivered = []
    monkeypatch.setattr("apps.accounts.services_registration.send_email_verification_otp",
                        lambda address, code: delivered.append(address) or 1)
    response = APIClient().post(reverse("auth-member-sign-up"), {
        "email": email, "password": NEW_PASSWORD, "display_name": "Community account", "phone": "",
    }, format="json")
    assert response.status_code == 200, response.data
    assert set(response.data) == {"detail"} and "access" not in response.data
    member = User.objects.get(account_kind="member", email=email)
    assert member.pk != employee.pk and member.check_password(NEW_PASSWORD)
    assert member.email_verified_at is None and member.email_challenges.filter(consumed_at__isnull=True).exists()
    assert delivered == [email]
    employee.refresh_from_db()
    assert employee.account_kind == "staff" and employee.check_password(PASSWORD)
    assert not employee.email_challenges.exists() and not employee.makerspace_memberships.filter(
        assigned_role__slug="member",
    ).exists()
