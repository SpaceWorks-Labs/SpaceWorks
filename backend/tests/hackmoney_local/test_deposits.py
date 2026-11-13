"""Hack-money G10: refundable deposits. Raised at confirmation, closed with the place, and returned only
through ONE staff-approved settlement batch that opens refund cases staff still decide (#59)."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.http import Http404
from django.utils import timezone

from apps.events.judging import deposits, options
from apps.events.judging.errors import ProgrammeError
from apps.events.models import Event, EventRegistration
from apps.events.service_payments import create_for_registered_registration
from apps.payments.models import Payment, RefundCase
from tests.events.ticketing_helpers import account
from tests.hackmoney_local.helpers import command, enable, world  # noqa: F401

pytestmark = pytest.mark.django_db
VOID = ("canceled", "cancelled")


def deposits_on(world, amount="500.00", **fields):
    enable(world, "events.deposits")
    options.update(world.event.pk, actor=world.manager, data=command(0, deposit_amount=amount, **fields))


def place(world, status="registered", *, crew=False):
    member = account(f"hacker-{uuid4().hex[:8]}")
    row = EventRegistration.objects.create(event=world.event, member=member, name=member.username, email=member.email,
                                           phone=member.phone, status=status, **({"is_crew": True} if crew else {}))
    create_for_registered_registration(row, world.manager)
    return row


def deposit(row):
    return Payment.objects.filter(subject_type="event_deposit", subject_id=row.pk).first()


def end_event(world):
    past = timezone.now() - timedelta(days=2)
    Event.objects.filter(pk=world.event.pk).update(starts_at=past, ends_at=past + timedelta(hours=8))
    world.event.refresh_from_db()


def options_version(world):
    return options.projection(world.event)["version"]


def test_off_by_default_nothing_is_charged(world):
    options.update(world.event.pk, actor=world.manager, data=command(0, results_email=True))
    assert deposit(place(world)) is None


def test_setting_a_deposit_needs_the_capability(world):
    with pytest.raises(ProgrammeError) as off:
        options.update(world.event.pk, actor=world.manager, data=command(0, deposit_amount="500.00"))
    assert off.value.detail["code"] == "feature_disabled"


def test_a_confirmed_place_owes_one_deposit_on_its_member_never_crew(world):
    deposits_on(world)
    row = place(world)
    payment = deposit(row)
    assert (payment.amount, payment.member_id, payment.status) == (Decimal("500.00"), row.member_id, "pending")
    create_for_registered_registration(row, world.manager)  # idempotent
    assert Payment.objects.filter(subject_type="event_deposit", subject_id=row.pk).count() == 1
    assert deposit(place(world, crew=True)) is None


def test_a_cancelled_place_voids_a_pending_deposit_and_a_paid_one_opens_a_case(world, django_capture_on_commit_callbacks):
    from apps.events.services_lifecycle import _cancel_open_charges_after_commit
    deposits_on(world)
    pending, paid = place(world), place(world)
    Payment.objects.filter(pk=deposit(paid).pk).update(status="paid_offline")
    with django_capture_on_commit_callbacks(execute=True):
        _cancel_open_charges_after_commit(world.event, world.manager, registration_ids=(pending.pk, paid.pk))
    assert deposit(pending).status in VOID
    case = RefundCase.objects.get(payment=deposit(paid))
    assert case.reason_code == "registration_cancelled" and deposit(paid).status == "paid_offline"


def test_cancelling_the_event_closes_every_deposit(world, django_capture_on_commit_callbacks):
    from apps.events.programme_charges import close_for_cancelled_event
    deposits_on(world)
    paid = place(world)
    Payment.objects.filter(pk=deposit(paid).pk).update(status="paid_online")
    with django_capture_on_commit_callbacks(execute=True):
        close_for_cancelled_event(world.event, world.manager)
    assert RefundCase.objects.get(payment=deposit(paid)).reason_code == "event_cancelled"


def test_settlement_returns_attendees_keeps_no_shows_and_moves_no_money(world, django_capture_on_commit_callbacks):
    deposits_on(world)
    came, stayed_home, came_unpaid = place(world), place(world), place(world)
    for row in (came, stayed_home):
        Payment.objects.filter(pk=deposit(row).pk).update(status="paid_offline")
    EventRegistration.objects.filter(pk__in=[came.pk, came_unpaid.pk]).update(status="attended")
    end_event(world)
    outcomes = {row["registration_id"]: row["outcome"] for row in deposits.plan(world.event)}
    assert outcomes == {came.pk: "return", stayed_home.pk: "keep", came_unpaid.pk: "void"}
    with django_capture_on_commit_callbacks(execute=True):
        result = deposits.settle(world.event.pk, actor=world.manager, data=command(options_version(world)))
    assert result["settled_at"] is not None
    case = RefundCase.objects.get(payment=deposit(came))
    assert (case.kind, case.reason_code, case.due_amount) == ("due", "deposit_returned", Decimal("500.00"))
    assert deposit(came).status == "paid_offline"  # a staff decision on the case refunds it, never the batch
    assert not RefundCase.objects.filter(payment=deposit(stayed_home)).exists()
    assert deposit(stayed_home).status == "paid_offline" and deposit(came_unpaid).status in VOID
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(action="event.deposit.forfeited").count() == 1


def test_settlement_can_require_a_submission(world):
    deposits_on(world, deposit_requires_submission=True)
    row = place(world)
    Payment.objects.filter(pk=deposit(row).pk).update(status="paid_offline")
    EventRegistration.objects.filter(pk=row.pk).update(status="attended")
    assert deposits.plan(world.event)[0]["outcome"] == "keep"  # came, but sealed in no submitted project


def test_settlement_runs_once_and_only_after_the_event(world):
    deposits_on(world)
    place(world)
    with pytest.raises(ProgrammeError) as early:
        deposits.settle(world.event.pk, actor=world.manager, data=command(options_version(world)))
    assert early.value.detail["code"] == "event_not_ended"
    end_event(world)
    deposits.settle(world.event.pk, actor=world.manager, data=command(options_version(world)))
    with pytest.raises(ProgrammeError) as twice:
        deposits.settle(world.event.pk, actor=world.manager, data=command(options_version(world)))
    assert twice.value.detail["code"] == "already_settled"
    with pytest.raises(ProgrammeError):
        options.update(world.event.pk, actor=world.manager, data=command(options_version(world), deposit_amount="900.00"))


def test_only_payment_recorders_or_the_event_manager_settle(world):
    deposits_on(world)
    end_event(world)
    with pytest.raises(Http404):
        deposits.settle(world.event.pk, actor=world.judges[0], data=command(options_version(world)))


def test_the_deposit_subject_is_in_every_money_touchpoint():
    from apps.payments.availability import SUBJECT_DOMAINS
    from apps.payments.finance_scope import PAYMENT_DOMAINS
    from apps.payments.models import Payment as P
    from apps.payments.reconciliation_authority import SUBJECT_ACTIONS
    from apps.tenant_migration.references import PAYMENT_SUBJECT_REFERENCES
    assert SUBJECT_DOMAINS["event_deposit"] == PAYMENT_DOMAINS["event_deposit"] == "events"
    assert PAYMENT_SUBJECT_REFERENCES["event_deposit"] == "events.EventRegistration"
    assert "event_deposit" in P.EVENT_SUBJECT_TYPES and P.SubjectType.EVENT_DEPOSIT in SUBJECT_ACTIONS


def test_missing_options_resolve_nullable_fees_and_json_projection(world):
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    from apps.events.judging.models_options import HackathonProgrammeOptions

    assert not HackathonProgrammeOptions.objects.filter(event=world.event).exists()
    for key in ("deposit_amount", "entry_fee", "team_fee", "prize_claim_days"):
        assert options.option(world.event, key) is None
    projection = options.projection(world.event)
    assert projection["deposit_amount"] is None and projection["entry_fee_stage"] == 1
    assert projection["results_email"] is False
    json.dumps(projection, cls=DjangoJSONEncoder)  # no NOT_PROVIDED class/callable escapes
    assert not HackathonProgrammeOptions.objects.filter(event=world.event).exists()


def test_missing_options_evaluate_callable_defaults(world, monkeypatch):
    from django.db import models
    from apps.events.judging.models_options import HackathonProgrammeOptions

    original = HackathonProgrammeOptions._meta.get_field
    callable_field = models.PositiveSmallIntegerField(default=lambda: 4)
    monkeypatch.setattr(HackathonProgrammeOptions._meta, "get_field",
        lambda key: callable_field if key == "entry_fee_stage" else original(key))
    assert options.option(world.event, "entry_fee_stage") == 4
    assert options.projection(world.event)["entry_fee_stage"] == 4


@pytest.mark.parametrize("amount", ["0.00", "15.00"])
def test_ordinary_registration_with_deposits_enabled_and_no_options_adds_no_deposit(settings, amount):
    from apps.events.judging.models_options import HackathonProgrammeOptions
    from apps.events.services_registration import register
    from tests.events.ticketing_helpers import event_space, open_event

    settings.PII_ENCRYPTION_ENABLED = False
    space = event_space("no-options-" + uuid4().hex[:10])
    space.enabled_features = sorted(set(space.enabled_features) | {"events.hackathons", "events.deposits"})
    space.save(update_fields=["enabled_features"])
    event = open_event(space, payment_amount=Decimal(amount))
    from apps.makerspaces.platform import feature_enabled
    assert feature_enabled(space, "events.deposits"), "Exercise the enabled deposit seam"
    member = account("no-options-member-" + uuid4().hex[:10])
    assert not HackathonProgrammeOptions.objects.filter(event=event).exists()
    row = register(event, member=member, actor=member)
    assert row.status == EventRegistration.Status.REGISTERED
    assert not Payment.objects.filter(makerspace=space, subject_type="event_deposit").exists()
    charges = list(Payment.objects.filter(makerspace=space))
    if Decimal(amount):
        assert len(charges) == 1
        assert (charges[0].subject_type, charges[0].amount, charges[0].status) == (
            "event_registration", Decimal(amount), "pending")
    else:
        assert charges == []
    assert not HackathonProgrammeOptions.objects.filter(event=event).exists()
