"""Journey steps call real services; time travel changes only the clock."""
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from django.utils import timezone
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.events.contracts.providers import LockedContext
from apps.events.programme_locks import fences
from apps.events.services_registration import register
from apps.events.services_checkin import mark_attended_with_event
from apps.events.hackathons.admission_workflow import save_application
from apps.events.hackathons.admission_rsvp import rsvp
from apps.event_reimbursements import request_workflow, award_workflow, claim_workflow
from apps.event_reimbursements.request_form_adapter import prepare
from apps.event_reimbursements.models import GrantRequest, GrantAward, ReimbursementClaim
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from .conftest import cmd


def block(world, amount=10000):
    p, e = world.programme, world.event
    return {"submit": True, "programme_id": p.pk, "programme_version": p.version,
        "form": {"schema_version": 2, "form_id": f"reimbursement-request-{p.pk}", "revision": p.version},
        "estimates": [{"category": "rail", "amount_minor": amount, "currency": "INR"}],
        "itinerary": {"mode": "rail", "origin": "Kochi", "destination": "Bengaluru",
            "depart_at": (e.starts_at - timedelta(days=1)).isoformat(), "arrive_at": e.starts_at.isoformat()},
        "need_statement": "Private support statement", "distance_km": "550.000"}


def participate(world):
    if world.hackathon:
        app, _ = save_application(event=world.event, actor=world.owner, submit=True,
            payload=cmd(event_date_revision=world.event.event_date_revision,
                form={"schema_version": 2, "form_id": "application", "revision": 1}, answers={}, derivations={},
                save_choices={}, saved_detail_versions={}, coc={"revision": 1, "accepted": True}))
        assert app.state == "offered"
        rsvp(event_id=world.event.pk, actor=world.owner, data=cmd(app.version, decision="accept"))
        app.refresh_from_db()
        assert app.state == "confirmed"
        return app.registration
    return register(world.event, member=world.owner, actor=world.owner)


def requested(world, *, inline=False, amount=10000):
    value = block(world, amount)
    if inline:
        # The request travels with the signup itself (events.inline_forms).
        register(world.event, member=world.owner, actor=world.owner,
                 inline_forms={"operation_id": uuid4(), "reimbursement_request": value})
        return GrantRequest.objects.get(event=world.event, member=world.owner)
    participate(world)
    request_workflow.submit(event_id=world.event.pk, actor=world.owner, request=world.member_session,
        data=cmd(reimbursement_request=value))
    return GrantRequest.objects.get(event=world.event, member=world.owner)


def accepted(world, *, amount=10000, inline=False):
    grant = requested(world, inline=inline, amount=amount)
    world.pool.refresh_from_db()
    award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk,
        data=cmd(grant.version, expected_award_version=None, expected_pool_version=world.pool.version,
            outcome="award", amount_minor=amount, currency="INR", reason_code="need_based"))
    award = GrantAward.objects.get(request=grant)
    award_workflow.respond(event_id=world.event.pk, actor=world.owner, request=world.member_session,
        data=cmd(award.version, award_revision=award.revisions.get().revision), accept=True)
    award.refresh_from_db()
    return award


def receipt(world, claim, amount, *, digest="a" * 64):
    identity = uuid4().hex
    return FinanceAttachment.objects.create(makerspace=world.space, event=world.event, event_id_snapshot=world.event.pk,
        event_title_snapshot=world.event.title, owner_member=world.owner, purpose="reimbursement_receipt",
        binding_kind="claim", binding_uuid=claim.uuid, question_id="receipt", state="ready", expected_bytes=10,
        actual_bytes=10, declared_mime="application/pdf", canonical_mime="application/pdf", sha256=digest,
        original_filename="private-receipt.pdf", staging_key="finance/staging/" + identity,
        object_key="finance/final/" + identity, scan_status="clean", scanner_policy="test",
        retention_policy_revision=1, retention_days_snapshot=2555)


def submitted(world, monkeypatch, *, amount=10000, inline=False, award=None, receipt_total=None):
    award = award or accepted(world, amount=amount, inline=inline)
    original_now = timezone.now()
    attended = world.event.starts_at + timedelta(hours=1)
    # Time is advanced to exercise the real check-in and claim writers.
    monkeypatch.setattr(timezone, "now", lambda: attended)
    registration, checkin = mark_attended_with_event(award.request.registration, actor=world.manager, source="qr")
    after = world.event.ends_at + timedelta(days=1)
    monkeypatch.setattr(timezone, "now", lambda: after)
    from tests.accounts.test_reauthentication import request as session_request, PASSWORD
    from apps.accounts import reauthentication
    world.finance = session_request(world.manager)
    reauthentication.verify(world.finance, password=PASSWORD)
    world.member_session = session_request(world.owner, surface="member")
    claim = ReimbursementClaim.objects.create(award=award, event=world.event, member=world.owner,
        effective_due_at=world.programme.claim_due_at)
    asset = receipt(world, claim, amount)
    line_id = uuid4()
    line = {"line_uuid": line_id, "category": "rail", "vendor": "Private vendor", "description": "Travel",
        "traveller": "Private traveller", "expense_date": world.event.starts_at.date(), "original_amount_minor": amount,
        "original_currency": "INR", "fx_rate": "1.000000000000", "rate_date": world.event.starts_at.date(),
        "rate_source": "receipt", "source_note": "", "route": {"origin": "Kochi", "destination": "Bengaluru", "mode": "rail"},
        "receipt": {"asset_id": asset.pk, "generation": 1, "sha256": asset.sha256, "receipt_total_minor": receipt_total or amount}}
    claim_workflow.save_draft(event_id=world.event.pk, actor=world.owner,
        request=world.member_session, data=cmd(claim.version, lines=[line]))
    claim.refresh_from_db()
    claim_workflow.submit(event_id=world.event.pk, actor=world.owner, request=world.member_session,
        data=cmd(claim.version, current_revision=None))
    claim.refresh_from_db()
    return claim, asset, line_id


def decision_data(world, claim, line_id, amount, *, outcome="approved", **overrides):
    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    claim.refresh_from_db(); world.pool.refresh_from_db()
    ob = EventPayoutObligation.objects.filter(source_uuid=claim.uuid).first()
    registration = claim.award.request.registration
    return cmd(claim.version, mode="decide", expected_pool_version=world.pool.version,
        expected_decision_sequence=claim.decisions.count(), expected_obligation_version=ob.version if ob else None,
        claim_revision_id=claim.current_revision_id, outcome=outcome, line_decisions=[{
            "line_uuid": line_id, "approved_minor": amount, "reason_code": "approved" if outcome == "approved" else "policy_cap"}],
        eligibility_revision=registration.attendance_revision, reason_code="approved" if outcome == "approved" else "policy_cap",
        note="Private financial explanation", **overrides)
