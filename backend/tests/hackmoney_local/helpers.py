"""Shared hack-money test world: the L21b pairwise world with charge tracking on."""
from decimal import Decimal

import pytest

from apps.events.programme_charges import raise_charge
from apps.events.submissions.models_projects import HackathonSubmission
from apps.payments.models import Payment
from tests.events.pairwise_helpers import command, pairwise_world  # noqa: F401  (re-exported)


def enable(world, *keys):
    world.space.enabled_features = sorted(set(world.space.enabled_features) | set(keys))
    world.space.save(update_fields=["enabled_features"])


@pytest.fixture
def world(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=2, judges=3, enabled=False)
    enable(world, "charges.enabled", "charges.events")
    return world


def projects(world):
    return list(HackathonSubmission.objects.filter(event=world.event).select_related("team").order_by("pk"))


def paid_fee(world, project, amount="500.00", status="paid_offline"):
    payment = raise_charge(event=world.event, subject_type="submission_fee", subject_id=project.pk,
                           member=project.team.leader, amount=amount, actor=project.team.leader,
                           audit_action="event.submission.fee_raised", target={})
    if status != "pending":
        Payment.objects.filter(pk=payment.pk).update(status=status)
    return payment


def team_charge(world, team, amount="1500.00", status="paid_online"):
    payment = raise_charge(event=world.event, subject_type="team_registration", subject_id=team.pk, member=team.leader,
                           amount=amount, actor=team.leader, audit_action="event.team.payment_raised", target={})
    if status != "pending":
        Payment.objects.filter(pk=payment.pk).update(status=status)
    return payment


def money(value):
    return Decimal(str(value))
