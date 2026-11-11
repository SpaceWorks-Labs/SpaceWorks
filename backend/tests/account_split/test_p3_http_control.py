"""HTTP contract, recent proof, old writer closure, and /control/ lifecycle paths."""
import pytest
from django.contrib import admin
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_services as service
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from .p3_helpers import PASSWORD, base, client, context

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def ctx(settings):
    return context(settings)


def test_shared_http_contract_list_create_policy_and_capabilities(ctx):
    api = client(ctx.manager)
    policy = api.get(base(ctx.space) + "policy")
    assert policy.status_code == 200
    assert not policy.data["can_manage_space_managers"]
    assert set(policy.data["creatable_roles"]) == {
        "inventory_manager", "machine_manager", "event_manager", "booking_manager", "handover"}
    created = api.post(base(ctx.space), {"display_name": "New", "username": "new",
        "roles": ["event_manager", "booking_manager"], "machine_type_ids": []}, format="json")
    assert created.status_code == 201, created.data
    account = created.data["account"]
    assert created.data["invitation_sent"] is False
    assert set(account) == {"id", "username", "display_name", "email", "roles", "machine_type_ids",
        "is_active", "must_change_password", "mfa_enabled", "last_login", "created_at", "invitation_pending", "can"}
    assert account["username"] == "new.p3" and account["must_change_password"]
    listed = api.get(base(ctx.space))
    assert listed.status_code == 200 and set(listed.data) == {"count", "next", "previous", "results"}
    own = next(row for row in listed.data["results"] if row["id"] == ctx.manager.pk)
    assert not any(own["can"].values())
    target = account["id"]
    patched = api.patch(f"{base(ctx.space)}{target}/", {"roles": ["handover"], "machine_type_ids": []}, format="json")
    assert patched.status_code == 200 and patched.data["roles"] == ["handover"]
    password = api.post(f"{base(ctx.space)}{target}/set-password/", {"generate": True}, format="json")
    assert password.status_code == 200 and password.data["generated_password"]
    assert "no-store" in password["Cache-Control"]
    assert api.post(f"{base(ctx.space)}{target}/deactivate/", {"reason": "Finished"}, format="json").status_code == 200
    assert target not in [row["id"] for row in api.get(base(ctx.space)).data["results"]]
    assert target in [row["id"] for row in api.get(base(ctx.space) + "?include_inactive=1").data["results"]]
    assert api.post(f"{base(ctx.space)}{target}/reactivate/", {}, format="json").status_code == 200


def test_create_emails_only_an_initial_setup_link_after_commit(ctx, monkeypatch):
    from types import SimpleNamespace
    from django.db import connection
    from apps.accounts.models import StaffInvitation
    sent = []
    def dispatch(**kwargs):
        assert not connection.in_atomic_block
        assert kwargs["persist_body"] is False
        assert "Set the initial password" in kwargs["text_body"]
        sent.append(kwargs)
        return SimpleNamespace(status="sent")
    monkeypatch.setattr("apps.accounts.staff_invitation_delivery.dispatch_email", dispatch)
    response = client(ctx.manager).post(base(ctx.space), {"display_name": "Email staff",
        "email": "onboard@example.test", "roles": ["handover"]}, format="json")
    assert response.status_code == 201 and response.data["invitation_sent"]
    row = StaffInvitation.objects.get(account_id=response.data["account"]["id"])
    assert row.role_snapshot == ["handover"] and row.credential_generation == 0
    assert response.data["account"]["invitation_pending"]
    assert sent[0]["to_email"] == "onboard@example.test"
    assert "accept_url" not in response.data and "generated_password" not in response.data


@pytest.mark.parametrize("suffix,method", [("", "post"), ("{id}/", "patch"),
    ("{id}/deactivate/", "post"), ("{id}/reactivate/", "post"),
    ("{id}/set-password/", "post"), ("{id}/resend-invite/", "post")])
def test_all_new_mutations_require_recent_reauthentication(ctx, suffix, method):
    response = getattr(client(ctx.manager, recent=False), method)(
        base(ctx.space) + suffix.format(id=ctx.worker.pk), {}, format="json")
    assert response.status_code == 403 and response.data["code"] == "recent_reauth_required"


@pytest.mark.parametrize("suffix", ["", "policy"])
def test_contract_reads_require_recent_proof_too(ctx, suffix):
    response = client(ctx.manager, recent=False).get(base(ctx.space) + suffix)
    assert response.status_code == 403 and response.data["code"] == "recent_reauth_required"


def test_tenant_gate_and_cross_tenant_origin_refuse_before_mutation(ctx):
    from tests.tenant_migration.source_gate_helpers import close_gate
    api = client(ctx.manager)
    before = ctx.worker.password
    assert api.post(f"{base(ctx.other)}{ctx.worker.pk}/set-password/", {"generate": True}, format="json").status_code == 404
    close_gate(ctx.space, ctx.root)
    assert api.post(f"{base(ctx.space)}{ctx.worker.pk}/set-password/", {"generate": True}, format="json").status_code == 423
    ctx.worker.refresh_from_db()
    assert ctx.worker.password == before and ctx.worker.credential_generation == 0


def test_every_old_staff_creation_writer_is_refused(ctx):
    from apps.admin_api.services_staff import attach_staff_membership
    from apps.admin_api.services_user_access import reset_user_password
    from apps.makerspaces.membership_legacy import invite_membership
    from apps.makerspaces.membership_self_service import leave_makerspace
    from apps.makerspaces.self_service_access import own_membership
    role = ctx.space.roles.get(slug="handover")
    api = client(ctx.manager)
    before = User.objects.count()
    assert api.post("/api/v1/admin/users/handover", {"username": "old", "makerspace_id": ctx.space.pk,
        "role": "handover"}, format="json").status_code == 400
    assert api.post(f"/api/v1/admin/makerspaces/{ctx.space.pk}/memberships", {"username": "old",
        "role_id": role.pk}, format="json").status_code == 400
    operations = [lambda: attach_staff_membership(actor=ctx.manager, makerspace=ctx.space, username="old", role=role),
                  lambda: reset_user_password(ctx.root, ctx.worker.pk),
                  lambda: invite_membership(ctx.manager, ctx.space, "old@example.test", role),
                  lambda: leave_makerspace(ctx.manager, ctx.space.pk, "Leaving"),
                  lambda: own_membership(ctx.manager, ctx.space.pk)]
    for operation in operations:
        with pytest.raises(APIException):
            operation()
    assert User.objects.count() == before and ctx.worker.is_active


def test_old_delete_routes_deactivate_without_deleting_membership(ctx):
    response = client(ctx.manager).delete(f"/api/v1/admin/memberships/{ctx.membership.pk}")
    assert response.status_code == 204
    ctx.worker.refresh_from_db(); ctx.membership.refresh_from_db()
    assert not ctx.worker.is_active and ctx.membership.status == "revoked"
    assert AuditLog.objects.filter(action="staff_account.deactivated", target_id=str(ctx.worker.pk)).exists()


def test_control_guards_staff_fields_password_bulk_and_delete(ctx):
    account_admin = admin.site._registry[User]
    request = RequestFactory().get("/control/"); request.user = ctx.root
    assert {"is_active", "account_kind", "staff_makerspace"} <= set(account_admin.get_readonly_fields(request, ctx.worker))
    assert not account_admin.has_delete_permission(request, ctx.worker)
    assert not account_admin.has_delete_permission(request, ctx.root)
    for queryset in [User.objects.filter(pk=ctx.worker.pk), User.objects.filter(pk=ctx.root.pk)]:
        with pytest.raises(DjangoPermissionDenied):
            account_admin.delete_queryset(request, queryset)
        with pytest.raises(DjangoPermissionDenied):
            account_admin.restrict_access(request, queryset)


def test_control_real_create_password_and_deactivate_paths(ctx, client):
    from tests.accounts.reauth_helpers import force_recent_control_login
    force_recent_control_login(client, ctx.root)
    create_url = reverse("admin:makerspaces_makerspace_create_staff_account", args=[ctx.space.pk])
    assert client.get(create_url).status_code == 200
    response = client.post(create_url, {"display_name": "Control staff", "username": "control",
        "roles": ["inventory_manager"], "machine_type_ids": []})
    assert response.status_code == 302
    target = User.objects.get(username="control.p3")
    password_url = reverse("admin:auth_user_password_change", args=[target.pk])
    assert client.get(password_url).status_code == 403
    users_url = reverse("admin:accounts_user_changelist")
    reset = client.post(users_url, {"action": "set_staff_password", "_selected_action": [target.pk], "index": "0"})
    assert reset.status_code == 200 and reset.context_data["generated_password"]
    target.refresh_from_db()
    assert target.check_password(reset.context_data["generated_password"])
    assert "no-store" in reset["Cache-Control"]
    removed = client.post(users_url, {"action": "deactivate_staff_account", "_selected_action": [target.pk], "index": "0"})
    assert removed.status_code == 302
    target.refresh_from_db()
    assert not target.is_active
