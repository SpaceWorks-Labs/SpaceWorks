from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.messages import get_messages
from django.test import Client, override_settings
from django.urls import reverse
import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.boxes.models import QrCode
from apps.integrations.models import EmailLog
from apps.inventory.models import InventoryAsset, TrackingMode
from tests.return_helpers import make_member, make_product, make_space, make_user
from tests.accounts.reauth_helpers import force_recent_control_login as force_mfa_login

pytestmark = pytest.mark.django_db


def make_superadmin(username="admin-parity-super"):
    return make_user(
        username, role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE,
        is_staff=True, is_superuser=True,
    )


def admin_client(user=None):
    client = Client()
    force_mfa_login(client, user or make_superadmin())
    return client


def post_action(client, url, action, obj, **extra):
    # #188: dangerous actions ask to confirm first; these tests exercise the confirmed post.
    data = {"action": action, ACTION_CHECKBOX_NAME: [str(obj.pk)], "index": "0", "control_confirmed": "yes", **extra}
    return client.post(url, data, follow=True)


def make_qr(product, actor):
    return QrCode.objects.create(
        makerspace=product.makerspace, target_type=QrCode.TargetType.PRODUCT,
        target_id=product.id, created_by=actor,
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_email_retry_action_routes_through_service_and_rejects_non_failed():
    client = admin_client(make_superadmin("admin-parity-email-super"))
    url = reverse("admin:integrations_emaillog_changelist")
    failed = EmailLog.objects.create(
        to_email="retry@example.com", subject="Retry", text_body="hello",
        stream="printing", event="failed", status=EmailLog.Status.FAILED,
        error="smtp down",
    )
    sent = EmailLog.objects.create(
        to_email="sent@example.com", subject="Sent", text_body="hello",
        status=EmailLog.Status.SENT,
    )

    retry_response = post_action(client, url, "retry_selected", failed)
    reject_response = post_action(client, url, "retry_selected", sent)

    assert retry_response.status_code == 200
    assert reject_response.status_code == 200
    failed.refresh_from_db()
    sent.refresh_from_db()
    assert failed.status in {EmailLog.Status.PENDING, EmailLog.Status.SENT}
    assert sent.status == EmailLog.Status.SENT
    assert AuditLog.objects.filter(action="email.retried", target_id=str(failed.id)).exists()
    assert AuditLog.objects.filter(action="email.retried", target_id=str(sent.id)).count() == 0


def test_user_admin_password_reset_reveals_temp_password_once_and_audits():
    space = make_space("admin-parity-reset")
    target = make_member("admin-parity-reset-target", space,
        membership_role="inventory_manager", role=User.Role.REQUESTER)
    # Stale since d7f674a7 (Q8, #66): the staff-only "set_staff_password" action is gone; one
    # person's password is reset by the superadmin through reset_password_selected, which shows the
    # temporary password once as an admin message and audits user.password_reset without it.
    response = post_action(admin_client(make_superadmin("admin-parity-reset-super")),
        reverse("admin:accounts_user_changelist"), "reset_password_selected", target)
    assert response.status_code == 200
    target.refresh_from_db()
    prefix = f"{target.username}: "
    shown = [str(m) for m in get_messages(response.wsgi_request) if str(m).startswith(prefix)]
    assert len(shown) == 1
    password = shown[0].removeprefix(prefix)
    assert password and target.check_password(password) and target.must_change_password
    assert "no-store" in response["Cache-Control"]
    event = AuditLog.objects.get(action="user.password_reset", target_id=str(target.pk))
    assert password not in str(event.meta)


def test_user_admin_password_reset_blocks_platform_staff():
    superadmin = make_superadmin("admin-parity-reset-guard-super")
    client = admin_client(superadmin)
    url = reverse("admin:accounts_user_changelist")
    super_target = make_superadmin("admin-parity-reset-super-target")

    post_action(client, url, "reset_password_selected", super_target)

    super_target.refresh_from_db()
    assert super_target.must_change_password is False


def test_needs_fix_repair_and_scrap_actions_mirror_api_transaction_and_audit():
    space = make_space("admin-parity-needs-fix")
    repair_product = make_product(
        space,
        name="Repairable",
        total_quantity=2,
        available_quantity=0,
        needs_fix_quantity=2,
    )
    scrap_product = make_product(
        space,
        name="Scrappable",
        total_quantity=2,
        available_quantity=0,
        needs_fix_quantity=2,
    )
    client = admin_client(make_superadmin("admin-parity-needs-fix-super"))
    url = reverse("admin:inventory_inventoryproduct_changelist")

    post_action(client, url, "repair_needs_fix", repair_product, apply="1", quantity="1")
    post_action(client, url, "scrap_needs_fix", scrap_product, apply="1", quantity="1")

    repair_product.refresh_from_db()
    scrap_product.refresh_from_db()
    assert (repair_product.needs_fix_quantity, repair_product.available_quantity) == (1, 1)
    assert (scrap_product.needs_fix_quantity, scrap_product.total_quantity) == (1, 1)
    assert AuditLog.objects.filter(action="inventory.needs_fix_repair").exists()
    assert AuditLog.objects.filter(action="inventory.needs_fix_scrap").exists()


def test_needs_fix_overdraw_is_rejected_without_side_effects():
    product = make_product(
        make_space("admin-parity-needs-fix-overdraw"),
        name="Overdraw",
        total_quantity=1,
        available_quantity=0,
        needs_fix_quantity=1,
    )
    post_action(
        admin_client(make_superadmin("admin-parity-needs-fix-overdraw-super")),
        reverse("admin:inventory_inventoryproduct_changelist"),
        "repair_needs_fix",
        product,
        apply="1",
        quantity="2",
    )

    product.refresh_from_db()
    assert (product.needs_fix_quantity, product.available_quantity) == (1, 0)
    assert not AuditLog.objects.filter(action="inventory.needs_fix_repair").exists()


def test_qr_revoke_and_rebind_actions_route_through_services():
    superadmin = make_superadmin("admin-parity-qr-super")
    space = make_space("admin-parity-qr")
    source = make_product(space, name="Source")
    rebind_source = make_product(space, name="Rebind Source")
    target = make_product(space, name="Target")
    revoke_qr = make_qr(source, superadmin)
    rebind_qr = make_qr(rebind_source, superadmin)
    client = admin_client(superadmin)
    url = reverse("admin:boxes_qrcode_changelist")

    post_action(client, url, "revoke_selected", revoke_qr)
    post_action(
        client,
        url,
        "rebind_selected",
        rebind_qr,
        apply="1",
        target_type=QrCode.TargetType.PRODUCT,
        product_target=str(target.id),
        new_name="Renamed Target",
    )

    revoke_qr.refresh_from_db()
    rebind_qr.refresh_from_db()
    target.refresh_from_db()
    assert revoke_qr.status == QrCode.Status.REVOKED
    assert rebind_qr.target_id == target.id
    assert target.name == "Renamed Target"
    assert AuditLog.objects.filter(action="qr.revoked", target_id=str(revoke_qr.id)).exists()
    assert AuditLog.objects.filter(action="qr.rebound", target_id=str(rebind_qr.id)).exists()


def test_qr_rebind_admin_rejects_cross_makerspace_non_product_target():
    superadmin = make_superadmin("admin-parity-qr-cross-super")
    source_space = make_space("admin-parity-qr-cross-source")
    dest_space = make_space("admin-parity-qr-cross-dest")
    source_product = make_product(source_space, name="Source Product")
    dest_product = make_product(
        dest_space,
        name="Asset Product",
        tracking_mode=TrackingMode.INDIVIDUAL,
        total_quantity=1,
        available_quantity=1,
    )
    dest_asset = InventoryAsset.objects.create(
        makerspace=dest_space,
        product=dest_product,
        asset_tag="DEST-ASSET-1",
    )
    qr = make_qr(source_product, superadmin)

    response = post_action(
        admin_client(superadmin),
        reverse("admin:boxes_qrcode_changelist"),
        "rebind_selected",
        qr,
        apply="1",
        target_type=QrCode.TargetType.ASSET,
        asset_target=str(dest_asset.id),
        new_name="DEST-ASSET-2",
    )

    qr.refresh_from_db()
    assert response.status_code == 200
    assert qr.makerspace_id == source_space.id
    assert qr.target_type == QrCode.TargetType.PRODUCT
    assert qr.target_id == source_product.id
    assert not AuditLog.objects.filter(action="qr.rebound").exists()
