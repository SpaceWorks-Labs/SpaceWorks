"""Prize-money test helpers: a published award whose winning snapshot seals two members."""
from decimal import Decimal

from apps.events.judging import payouts
from tests.hackmoney_local.helpers import command, enable


def winning_award(world, amount=Decimal("1000.00"), *, second_member=True, **prize_fields):
    """Enable the prize capabilities, publish one award, set prize kind/funding, seal a second member."""
    from apps.events.judging.models_definitions import HackathonPrize
    from apps.events.judging.models_results import EventAward
    from tests.l21b_local.test_money_and_switches import published_award
    enable(world, "events.prize_payouts", "events.prize_claims")
    if second_member:
        # The winning snapshot is immutable (DB trigger), so a two-member team is a project created with two
        # sealed members and swapped in as the first project; the original one-member project is dropped
        # from the world's port table so it is not judged.
        from tests.events.pairwise_helpers import _project
        old = world.snapshots[0]
        world.snapshots[0] = _project(world.event, world.ports, 99, mates=1)
        world.ports.snaps.pop(old)
    award = published_award(world, amount=amount)
    if prize_fields:
        HackathonPrize.objects.filter(pk=award.prize_id).update(**prize_fields)
        award = EventAward.objects.select_related("prize").get(pk=award.pk)
    members = list(world.ports.snaps[award.submission_snapshot_id].member_ids)
    return award, members


def user(pk):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.get(pk=pk)


def pay(world, award, recipient=None, check=False, **fields):
    data = command(0, award_id=award.pk, method="bank_transfer", reference="REF-1", paid_on="2026-11-05", **fields)
    if recipient is not None:
        data["recipient_id"] = recipient
    if not check:
        # These tests are about splits, tax and ledger effects; the verified-claim and maker-checker rules
        # (decision 301) have their own database tests in `parity_0120/fix_hack/test_payout_flows_db.py`.
        from unittest.mock import patch
        with patch("apps.events.judging.payout_checks.require_verified_claim"):
            return payouts.record_payout(world.event.pk, actor=world.manager, data=data)
    return payouts.record_payout(world.event.pk, actor=world.manager, data=data)


def payee(country="IN", method="upi", pan=""):
    body = {"country": country, "method": method, "details": {"holder_name": "Asha Winner", "upi_id": "asha@okbank"}}
    return {**body, "pan": pan} if pan else body


def accept_payees(settings, world, pairs=(("IN", "upi"), ("IN", "bank_transfer"))):
    """No operator policy (the ceiling is every supported pair); the Space Manager picks these (G13)."""
    from apps.payments.models import EventMoneySettings
    settings.EVENT_PAYOUT_TENANT_POLICIES = {}
    EventMoneySettings.objects.update_or_create(makerspace=world.space,
                                                defaults={"payee_templates": [list(pair) for pair in pairs]})


def tax_on(world, rate="30.00", threshold="10000.00"):
    from apps.payments.models import EventMoneySettings
    EventMoneySettings.objects.update_or_create(makerspace=world.space, defaults={
        "prize_tds_enabled": True, "prize_tds_rate": Decimal(rate), "prize_tds_threshold": Decimal(threshold)})
