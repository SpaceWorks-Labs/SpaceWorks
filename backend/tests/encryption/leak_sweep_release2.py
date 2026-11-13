"""Release-2 rows for the scoped-PII leak sweep (L4, L6, L18, L21a, L22, hack money, pairwise).

Each factory INSERTs one row whose mapped ``field`` already holds the sentinel, with the
smallest real parent graph the model and database guards accept. Several of these rows are
immutable after insert (stage reviews, pairwise comparisons), so nothing is written by update.
"""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.apps import apps
from django.utils import timezone

from tests.encryption import leak_sweep_programme as programme

EVENT_LABELS = {
    "events.JudgePairwiseComparison", "events.AdmissionStageReview", "events.EventAttendanceReply",
    "events.EventCrewMember", "events.HackathonPrizeClaim", "events.EventOrderSeat", "events.EventTicketTransfer",
}
SPACE_LABELS = {
    "makerspaces.MembershipRecord", "makerspaces.MembershipErasureRequest", "makerspaces.ImportedMember",
    "payments.Donation", "payments.DonorTaxDetail", "payments.DonationPledge", "payments.Sponsor", "shop.ShopOrder",
    # 0.12.0: minors/guardian consent (L3b), incidents (L3a/L16), equipment receipts (221b).
    "makerspaces.MinorProfile", "makerspaces.GuardianConsent", "maintenance.Incident",
    "inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt",
}


def model(label):
    return apps.get_model(label)


def _registration(w, member=None):
    stamp = uuid4().hex[:8]
    return model("events.EventRegistration").objects.create(
        event=w.event, member=member, name="Sweep", email=f"sweep-r2-{stamp}@example.test", phone="1")


def _second_snapshot(w):
    from apps.events.submissions.pii import prepare_documents
    team, _ = programme.led_team(w.event, programme.member("pairwise"))
    with prepare_documents(w.event.pk):
        submission = model("events.HackathonSubmission").objects.create(event=w.event, team=team)
        return model("events.SubmissionSnapshot").objects.create(
            submission=submission, sequence=1, submitted_by=team.leader, project={}, content_sha256="c" * 64)


def create_event(label, field, value, w):
    """Insert one release-2 event row of ``label``; raise KeyError for an unknown label."""
    e, s, now = w.event, w.space, w.now
    bound = {"event": e, "makerspace": s}
    if label == "events.JudgePairwiseComparison":
        judging = model("events.JudgingRound").objects.create(event=e, key=f"pair-{uuid4().hex[:6]}", mode="pairwise", state="open")
        judge = programme.role(w, "judge")
        previous, current = (
            model("events.JudgeAssignment").objects.create(event=e, round=judging, judge_role_assignment=judge,
                                                           submission_snapshot=snapshot)
            for snapshot in (w.snapshot, _second_snapshot(w)))
        return model(label).objects.create(**bound, round=judging, judge=judge, previous=previous, current=current,
                                           outcome="skip", submitted_at=now, sequence=1, **{field: value})
    if label == "events.AdmissionStageReview":
        stage = model("events.AdmissionStage").objects.create(event=e, position=1, name="Screen", state="open")
        assignment = model("events.AdmissionStageAssignment").objects.create(
            stage=stage, application=w.application, reviewer=programme.member("stage-reviewer"),
            plan_fingerprint="a" * 64)
        return model(label).objects.create(assignment=assignment, **{field: value})
    if label == "events.EventAttendanceReply":
        return model(label).objects.create(**bound, registration=_registration(w), asked_at=now, **{field: value})
    if label == "events.EventCrewMember":
        return model(label).objects.create(**bound, member=programme.member("crew"), **{field: value})
    if label == "events.HackathonPrizeClaim":
        prize = model("events.HackathonPrize").objects.create(event=e, name="Sweep prize", kind="cash",
                                                              funding="space", amount_per_winner=Decimal("10"))
        result = model("events.EventResultRevision").objects.create(
            event=e, version=1, algorithm_version="sweep", aggregates={}, content_sha256="d" * 64, finalized_at=now)
        award = model("events.EventAward").objects.create(result=result, prize=prize, prize_name=prize.name,
                                                          submission_snapshot=w.snapshot, rank=1)
        share = model("events.HackathonPrizeShare").objects.create(**bound, award=award, member=w.leader,
                                                                   amount=Decimal("10"))
        return model(label).objects.create(**bound, share=share, **{field: value})
    if label == "events.EventOrderSeat":
        buyer = programme.member("buyer")
        order = model("events.EventOrder").objects.create(makerspace=s, event=e, buyer=buyer, currency="INR")
        line = model("events.EventOrderLine").objects.create(order=order, kind="ticket", label="Seat", quantity=1,
                                                             unit_amount=0, line_total=0)
        return model(label).objects.create(**bound, order=order, line=line, **{field: value})
    if label == "events.EventTicketTransfer":
        holder = programme.member("transfer")
        return model(label).objects.create(makerspace=s, registration=_registration(w, holder), from_member=holder,
                                           expires_at=now + timedelta(days=1), **{field: value})
    raise KeyError(label)


# Mandatory-encrypted rows: written and read back inside the tenant's prepared key (see test_leak_sweep).
KEYED_LABELS = {"inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt"}


def new_space():
    from apps.makerspaces.models import Makerspace
    return Makerspace.objects.create(name="Sweep release 2", slug=f"sweep-r2-{uuid4().hex[:10]}")


def create_space_row(label, field, value, space=None):
    """Insert one release-2 makerspace row of ``label`` holding ``value`` in ``field``."""
    from apps.makerspaces.models import MakerspaceMembership
    stamp = uuid4().hex[:10]
    space = space or new_space()
    user = programme.member("sweep-r2")
    today = timezone.localdate()
    if label in {"makerspaces.MembershipRecord", "makerspaces.MembershipErasureRequest"}:
        membership = MakerspaceMembership.objects.create(
            makerspace=space, user=user, assigned_role=space.roles.get(slug="member"),
            role="custom", status="active", track="community")
        if label == "makerspaces.MembershipRecord":
            existing = model(label).objects.filter(membership=membership).first()
            if existing is not None:  # a membership may already own its record
                setattr(existing, field, value)
                existing.save(update_fields=[field])
                return existing
        return model(label).objects.create(makerspace=space, membership=membership, **{field: value})
    if label in {"makerspaces.ImportedMember", "payments.DonorTaxDetail"}:
        return model(label).objects.create(makerspace=space, **{field: value})
    if label == "payments.Donation":
        return model(label).objects.create(makerspace=space, amount=Decimal("10"), currency="INR", created_by=user,
                                           **{field: value})
    if label == "payments.DonationPledge":
        return model(label).objects.create(makerspace=space, amount=Decimal("10"), currency="INR", starts_on=today,
                                           next_due_on=today, created_by=user, **{field: value})
    if label == "payments.Sponsor":
        return model(label).objects.create(makerspace=space, name="Sweep sponsor", **{field: value})
    if label == "shop.ShopOrder":
        return model(label).objects.create(makerspace=space, pickup_code=stamp[:12], currency="INR", **{field: value})
    if label == "makerspaces.MinorProfile":
        return model(label).objects.create(makerspace=space, user=user, **{field: value})
    if label == "makerspaces.GuardianConsent":
        profile = model("makerspaces.MinorProfile").objects.create(makerspace=space, user=user)
        terms = model("makerspaces.GuardianConsentTerms").objects.create(makerspace=space, body="Terms", version="v1")
        return model(label).objects.create(
            makerspace=space, profile=profile, terms=terms, terms_version="v1", method="staff_recorded",
            signed_at=timezone.now(), valid_until=timezone.now() + timedelta(days=30), **{field: value})
    if label == "maintenance.Incident":
        return model(label).objects.create(makerspace=space, title="Sweep incident", **{field: value})
    if label in {"inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt"}:
        template = model("inventory.EquipmentKitTemplate").objects.create(makerspace=space, name="Kit")
        version = model("inventory.EquipmentKitVersion").objects.create(template=template, version=1, name="Kit", lines=[])
        plan = model("inventory.EquipmentConsumablePlan").objects.create(
            makerspace=space, borrower=user, kit_version=version, lines=[])
        if label == "inventory.EquipmentProposalReceipt":
            return model(label).objects.create(
                makerspace=space, borrower=user, operation_id=uuid4(), payload_sha256="0" * 64,
                outcome_kind="consumable_plan", consumable_plan=plan, imported_nonreplayable=True, **{field: value})
        from tests.test_request_workflow import make_product
        product = make_product(space, name="Sweep consumable", is_consumable=True)
        adjustment = model("operations.InventoryAdjustment").objects.create(
            makerspace=space, product=product, delta_available=-1, reason="Consumable used")
        return model(label).objects.create(
            makerspace=space, operation_id=uuid4(), product=product, quantity=1, payload_sha256="0" * 64,
            plan=plan, adjustment=adjustment, imported_nonreplayable=True, **{field: value})
    raise KeyError(label)
