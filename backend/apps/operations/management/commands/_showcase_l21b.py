"""Tinkerspace judging extras and hackathon money (release 2 L21b, #134 walkthrough).

Turns the L21b switches on and seeds, through the real services, on the showcase hackathon: a
"Best build" prize worth 5000 per winner, the per-event options (both emails on, refund on
disqualification, a 500 entry fee and a 1500 team price), and a draft "grand final" round (every
judge sees every project, fresh eyes) ready to receive finalists once "finals" is finalized in the
walkthrough. No payout or charge is invented: those are recorded by staff and members live.
"""

from uuid import uuid4

from apps.makerspaces.models import Makerspace

FEATURES = ("events.finalists", "events.prize_payouts", "events.entry_fees", "events.paid_teams",
            "events.saved_views", "events.gallery_search")


def _command(version=0, **values):
    return {"operation_id": uuid4(), "expected_version": version, **values}


def seed_l21b(space, manager, hackathon):
    from apps.events.judging.definitions_workflow import save_definition
    from apps.events.judging.options import update
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    Makerspace.objects.filter(pk=space.pk).update(enabled_features=space.enabled_features)
    save_definition(hackathon.pk, actor=manager, kind="prizes", data=_command(
        name="Best build", description="The build the judges would most like to take home.", amount_per_winner="5000.00"))
    from apps.events.judging.models_options import HackathonProgrammeOptions
    current = HackathonProgrammeOptions.objects.filter(event=hackathon).values_list("version", flat=True).first() or 0
    update(hackathon.pk, actor=manager, data=_command(current, results_email=True, submission_receipt_email=True,
                                                      refund_on_disqualification=True, entry_fee="500.00", team_fee="1500.00"))
    save_definition(hackathon.pk, actor=manager, kind="judging-rounds", data=_command(
        key="grand-final", mode="pairwise", min_reviews=3, visibility="all", fresh_eyes=True,
        guidance="Which project would you most want to see built for real?"))
