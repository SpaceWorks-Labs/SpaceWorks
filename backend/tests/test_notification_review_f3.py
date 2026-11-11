"""Review regressions: real mutation, audit, scope and owner delivery boundaries."""

from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import connection
from django.http import Http404
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.integrations import notify
from apps.integrations.destinations import _matches
from apps.integrations.models import NotificationPreference
from apps.machines.models import CertificationGrant, Machine
from apps.machines.notifications_certifications import notify_certification
from apps.machines.service_consumable_pools import create_pool
from apps.makerspaces.membership_notifications_research import notify_membership_decision
from apps.makerspaces.models import MembershipRequest
from apps.payments.models import Payment
from apps.payments.notifications import notify_payment
from apps.payments.services import create_payment
from apps.procurement.models import ToBuyItem
from apps.procurement.notifications import notify_stock
from apps.procurement.serializers import ToBuyItemSerializer
from apps.procurement.views_items import ToBuyDetailView
from tests.machines.certification_helpers import _certification, _machine_type, _manager, _member
from tests.return_helpers import authenticated_client, make_user
from tests.test_notification_families_f3 import capture_delivery, family_world
from tests.test_notification_family_edges_f3 import captured_events
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.destinations import NotificationScope

pytestmark = pytest.mark.django_db


def test_charge_audit_failure_rolls_back_debt_and_notification(monkeypatch, django_capture_on_commit_callbacks):
    space, manager, member, _payment = family_world("f3-review-charge")
    emails, channels = capture_delivery(monkeypatch)
    NotificationPreference.objects.create(makerspace=space, feature="payments", channel="email", enabled=True)
    subject = HardwareRequest.objects.create(
        makerspace=space, requester=member, requester_username=member.username,
    )

    def fail(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("apps.payments.services.audit.record", fail)
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            create_payment(makerspace=space, member=member, created_by=manager,
                           subject_type=Payment.SubjectType.LOAN_DEPOSIT, subject_id=subject.pk,
                           amount=Decimal("20.00"), currency="usd")
    assert not Payment.objects.filter(
        makerspace=space, subject_type=Payment.SubjectType.LOAN_DEPOSIT, subject_id=subject.pk,
    ).exists()
    assert Payment.objects.filter(makerspace=space).count() == 1
    assert emails == [] and channels == []


def test_revoke_locks_only_grant_and_replay_preserves_first_actor(monkeypatch, django_capture_on_commit_callbacks):
    space, manager, _owner, _payment = family_world("f3-review-revoke")
    machine_type = _machine_type(space)
    _user, membership = _member(space, "f3-review-cert-owner")
    grant = CertificationGrant.objects.create(
        certification_type=_certification(space, machine_type), membership=membership,
        notes="Original training",
    )
    client = authenticated_client(manager)
    events = captured_events(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        with CaptureQueriesContext(connection) as queries:
            first = client.post(reverse("admin-certification-grant-revoke", args=[grant.pk]),
                                {"notes": "First decision"}, format="json")
        # CaptureQueriesContext reads the connection log lazily. The next HTTP
        # request clears that log, so retain the first request SQL before replay.
        first_queries = list(queries.captured_queries)
        second = client.post(reverse("admin-certification-grant-revoke", args=[grant.pk]),
                             {"notes": "Second decision"}, format="json")
        assert events == []
    assert first.status_code == 200, first.data
    assert second.status_code == 400, second.data
    # This exercises the SQL on the HTTP path, including its related-object joins.
    import re
    lock_queries = [row["sql"] for row in first_queries if "FOR UPDATE OF" in row["sql"]]
    assert lock_queries
    grant_locks = []
    for sql in lock_queries:
        root = re.search(r'FROM "machines_certificationgrant"(?: ([A-Z]\d+))?', sql)
        if root:
            alias = root.group(1) or '"machines_certificationgrant"'
            locked = sql.split("FOR UPDATE OF ", 1)[1].strip()
            grant_locks.append(locked == alias)
    assert grant_locks and all(grant_locks)
    grant.refresh_from_db()
    assert grant.notes == "Original training" and grant.revoked_by_id == manager.pk
    assert AuditLog.objects.get(makerspace=space, action="certification.revoked").meta["notes"] == "First decision"
    assert AuditLog.objects.filter(makerspace=space, action="certification.revoked").count() == 1
    assert events == [("certifications", "revoked")]


def test_certification_type_audit_failure_rolls_back_creation(monkeypatch):
    from apps.machines.models import CertificationType
    space, manager, _owner, _payment = family_world("f3-review-type")
    machine_type = _machine_type(space)

    def fail(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("apps.admin_api.views_certification_types.audit.record", fail)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        authenticated_client(manager).post(reverse("admin-certification-types", args=[space.pk]),
                                           {"name": "New induction", "machine_type": machine_type.pk},
                                           format="json")
    assert not CertificationType.objects.filter(makerspace=space, name="New induction").exists()


def test_locked_procurement_rechecks_current_machine_type_before_retag(monkeypatch, django_capture_on_commit_callbacks):
    space, _staff, _owner, _payment = family_world("f3-review-retag")
    laser, printer = _machine_type(space, "Laser"), _machine_type(space, "Printer")
    manager, _role = _manager(space, "f3-review-laser-manager", laser)
    item = ToBuyItem.objects.create(makerspace=space, kind="printing", machine_type=laser, name="Stock")
    serializer = ToBuyItemSerializer(item, data={"status": "received", "machine_type": laser.pk}, partial=True)
    serializer.is_valid(raise_exception=True)
    # Simulate the other transaction completing between validation and row locking.
    ToBuyItem.objects.filter(pk=item.pk).update(machine_type=printer)
    view = ToBuyDetailView()
    view.request = SimpleNamespace(user=manager)
    emails, channels = capture_delivery(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(Http404):
            view.perform_update(serializer)
    item.refresh_from_db()
    assert item.status == "requested" and item.machine_type_id == printer.pk
    assert not AuditLog.objects.filter(makerspace=space, action="procurement.item_updated").exists()
    assert emails == [] and channels == []


def test_stock_scope_reaches_room_for_known_machine(monkeypatch, django_capture_on_commit_callbacks):
    space, manager, _owner, _payment = family_world("f3-review-stock-room")
    machine = Machine.objects.create(makerspace=space, machine_type=_machine_type(space), name="Laser")
    pool = create_pool(space, manager, material="PLA", initial_grams="100", machine=machine)
    item = ToBuyItem.objects.create(makerspace=space, kind="printing", name="Restock",
                                   machine_type=machine.machine_type, source_pool=pool)
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    with django_capture_on_commit_callbacks(execute=True):
        notify_stock(item, "low_stock")
    room = SimpleNamespace(
        machine_scopes=SimpleNamespace(all=lambda: [SimpleNamespace(machine_id=machine.pk)]),
        machine_type_scopes=SimpleNamespace(all=lambda: []),
        category_scopes=SimpleNamespace(all=lambda: []),
    )
    envelope = NotificationEnvelope.objects.get(makerspace=space, event="low_stock", audience="staff")
    scope = NotificationScope.from_dict(envelope.scope)
    assert _matches(room, scope)
    assert scope.machine_type_id == machine.machine_type_id


def test_membership_decline_uses_account_address_not_invite_contact(monkeypatch, django_capture_on_commit_callbacks):
    space, manager, _owner, _payment = family_world("f3-review-decline")
    owner = make_user("f3-review-applicant", access_status="active")
    owner.email_verified_at = timezone.now()
    owner.save(update_fields=["email_verified_at"])
    row = MembershipRequest.objects.create(makerspace=space, user=owner,
                                          invite_email="different@example.test", state="revoked", decided_by=manager)
    NotificationPreference.objects.create(makerspace=space, feature="members", channel="email", enabled=True)
    emails, _channels = capture_delivery(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        notify_membership_decision(row, "declined")
    assert [e["to_email"] for e in emails if e["audience"] == "requester"] == [owner.email]
    assert not any(e["to_email"] == row.invite_email for e in emails)


def test_certification_expiry_only_emails_its_member(monkeypatch, django_capture_on_commit_callbacks):
    space, _manager, _owner, _payment = family_world("f3-review-expiry")
    owner, membership = _member(space, "f3-review-expiry-owner")
    grant = CertificationGrant.objects.create(
        certification_type=_certification(space, _machine_type(space)),
        membership=membership, expires_at=timezone.now() + timedelta(days=1), notes="Private training notes",
    )
    owner.email_verified_at = timezone.now()
    owner.save(update_fields=["email_verified_at"])
    NotificationPreference.objects.create(makerspace=space, feature="certifications", channel="email", enabled=True)
    emails, _channels = capture_delivery(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        notify_certification(grant, "expiring")
    assert [e["to_email"] for e in emails if e["audience"] == "requester"] == [owner.email]
    assert all(grant.notes not in e["text_body"] for e in emails)


def test_owner_restriction_before_commit_suppresses_own_payment_email(monkeypatch, django_capture_on_commit_callbacks):
    from apps.accounts.models import User
    space, _manager, owner, payment = family_world("f3-review-restricted", payment_status="paid_online")
    NotificationPreference.objects.create(makerspace=space, feature="payments", channel="email", enabled=True)
    emails, _channels = capture_delivery(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        notify_payment(payment, "payment_received")
        User.objects.filter(pk=owner.pk).update(access_status=User.AccessStatus.RESTRICTED)
    assert not any(e["audience"] == "requester" for e in emails)


def test_zero_amount_snapshot_is_rendered_and_blank_owner_email_is_skipped(monkeypatch, django_capture_on_commit_callbacks):
    from apps.accounts.models import User
    space, _manager, owner, payment = family_world("f3-review-zero")
    # Rendering must preserve zero in a domain snapshot. The ledger requires a
    # positive charge, so exercise this defensively without persisting zero money.
    payment.amount = Decimal("0.00")
    NotificationPreference.objects.create(makerspace=space, feature="payments", channel="email", enabled=True)
    emails, _channels = capture_delivery(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        notify_payment(payment, "charge_raised")
    import json
    envelope = NotificationEnvelope.objects.get(recipient=owner, event="charge_raised")
    assert "0.00" in json.loads(envelope.message_body)["text"]
    # The worker rebuilds money from the immutable ledger, rather than trusting
    # the caller's in-memory defensive snapshot.
    assert "9876.54" in next(e["text_body"] for e in emails if e["audience"] == "requester")
    assert Payment.objects.get(pk=payment.pk).amount == Decimal("9876.54")
    emails.clear()
    User.objects.filter(pk=owner.pk).update(email="  ")
    with django_capture_on_commit_callbacks(execute=True):
        notify_payment(payment, "charge_raised")
    assert not any(e["audience"] == "requester" for e in emails)
    from apps.integrations.notification_resolution import email_eligible
    assert not email_eligible(envelope)


def test_split_certification_routes_have_auth_request_response_and_errors():
    from django.urls import include, path
    from drf_spectacular.generators import SchemaGenerator
    schema = SchemaGenerator(patterns=[
        path("api/v1/admin/", include("apps.admin_api.urls_certifications")),
    ]).get_schema(request=None, public=True)
    routes = {
        "/api/v1/admin/makerspace/{makerspace_id}/certification-types": ("get", "post"),
        "/api/v1/admin/certification-types/{id}": ("patch", "delete"),
        "/api/v1/admin/certification-types/{id}/grants": ("get", "post"),
        "/api/v1/admin/certification-grants/{id}/revoke": ("post",),
    }
    for route, methods in routes.items():
        for method in methods:
            operation = schema["paths"][route][method]
            assert operation["security"], (route, method)
            assert {"400", "401", "403", "404"} <= operation["responses"].keys()
            success = "201" if method == "post" and not route.endswith("revoke") else "200"
            assert operation["responses"][success]["content"]["application/json"]["schema"]
            if method in ("patch", "post"):
                assert operation["requestBody"]["content"]["application/json"]["schema"]
            if method != "get":
                assert "423" in operation["responses"]
