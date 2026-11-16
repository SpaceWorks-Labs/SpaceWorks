"""Portable export -> import into a fresh tenant for travel support, payouts and stage files.

Covers claims, awards, decisions, payouts, receipts and stage responses with files,
and proves payee bank data stays ciphertext in the archive and is rebound to the
target tenant key.
"""
import hashlib
import json
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connection
from django.utils import timezone

from apps.backup import storage as backup_storage
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.materialization import materialize_tenant
from apps.tenant_migration.object_export import capture_tenant_objects
from tests.encryption.conftest import enabled_encryption
from tests.event_reimbursements.conftest import cmd, make_world  # noqa: F401 - fixture
from tests.event_reimbursements.helpers import decision_data, submitted
from tests.tenant_migration.materialization_helpers import portable_import_case
from tests.tenant_migration.object_helpers import memory_objects  # noqa: F401 - fixture

pytestmark = pytest.mark.django_db(transaction=True)

PAYEE_SECRET = "918273645501234"
RECEIPT_BYTES = b"%PDF-1.7 receipt\n"


def _png():
    from PIL import Image
    data = BytesIO()
    Image.new("RGB", (2, 2)).save(data, format="PNG")
    return data.getvalue()


def _stage_file(world, monkeypatch):
    from apps.events.staged_forms import upload_jobs, upload_workflow
    from apps.events.staged_forms.response_workflow import prepare, save
    from apps.events.staged_forms.stage_workflow import activate_locked
    from apps.events.staged_forms.trigger_service import Participant
    from apps.events.staged_forms.upload_models import StageFormAsset
    from apps.events.models import EventRegistration
    from tests.events.staged_forms.conftest import definition, payload
    from tests.events.staged_forms.test_inline_submission import outer
    env = SimpleNamespace(space=world.space, event=world.event, owner=world.owner, now=timezone.now())
    registration = EventRegistration.objects.get(event=world.event, member=world.owner)
    row = definition(env, key="travel-docs", stage="post_event", due_after_seconds=7 * 86400,
        published_at=world.event.starts_at - timedelta(days=1), questions=[{"id": "file", "label": "File", "type": "file",
        "required": True, "file": {"purpose": "stage_form_file", "max_files": 1, "max_bytes_each": 10485760}}])
    from apps.encryption.preparation import prepare_tenants
    with prepare_tenants((world.space.pk,)), outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=Participant(event, world.owner.pk, registration, None), locks=locks)
    monkeypatch.setattr(upload_jobs, "scan_options", lambda: {"backend": "none"})

    class Presign:
        bucket = "test-private"
        def initialize(self, request):
            return SimpleNamespace(method="POST", url="https://upload.invalid", fields={"key": request.staging.key},
                expires_at=request.not_after, generation=request.generation)
    monkeypatch.setattr("apps.events.staged_forms.storage.storage", Presign)
    data = _png()
    created = upload_workflow.create(event_id=world.event.pk, stage_form_id=row.pk, actor=world.owner, data={
        "operation_id": uuid4(), "expected_version": assignment.version,
        "expected_response_version": assignment.response.version, "question_id": "file", "size_bytes": len(data),
        "mime": "image/png", "filename": "private-passport.png"})
    upload_workflow.complete(event_id=world.event.pk, stage_form_id=row.pk, actor=world.owner, asset_id=created["asset_id"],
        data={"operation_id": uuid4(), "expected_version": 1, "generation": 1})

    class Store:
        def read_uploaded(self, asset):
            return data, "staging-v1"
        def promote_bytes(self, asset, actual, digest):
            return "final-v1"
    assert upload_jobs.validate_asset(created["asset_id"], store=Store()) == "ready"
    asset = StageFormAsset.objects.get(pk=created["asset_id"])
    assignment.refresh_from_db()
    response = assignment.response
    body = payload(row, answers={"file": [{"asset_id": asset.pk, "generation": 1, "sha256": asset.sha256}]},
        operation_id=uuid4(), expected_version=response.version, expected_assignment_version=assignment.version)
    prepared = prepare(response=response, actor=world.owner, data=body, operation_id=body["operation_id"])
    save(event_id=world.event.pk, actor=world.owner, response_id=response.pk, data=body, prepared=prepared)
    asset.refresh_from_db()
    assert asset.state == "attached"
    return asset, data


def _keyed(request, data):
    request.META["HTTP_IDEMPOTENCY_KEY"] = str(data["operation_id"])
    request.__dict__.pop("headers", None)
    return request


def _payout(world, claim, line_id):
    from uuid import UUID
    from apps.event_reimbursements import claim_workflow
    from apps.payments.event_payouts import payee_workflow, payout_workflow
    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 7000, outcome="partially_approved"))
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    data = cmd(obligation.version, expected_payee_version=None, country="IN", method="bank_transfer",
        template_key="in_bank", template_version=1, details={"holder_name": "Private payee",
            "account_number": PAYEE_SECRET, "ifsc": "SBIN0000001", "bank_name": "Test bank"}, disclosure_version=1)
    result = payee_workflow.put(request=_keyed(world.member_session, data), obligation_id=obligation.pk, data=data)
    obligation.refresh_from_db()
    payee_id = UUID(result["payee_revision_id"])
    data = cmd(obligation.version, payee_revision_id=payee_id, expected_payee_version=result["payee_version"])
    payee_workflow.review(request=_keyed(world.finance, data), obligation_id=obligation.pk, verified=True, data=data)
    obligation.refresh_from_db()
    from apps.payments.event_payouts import eligibility_workflow
    data = cmd(obligation.version, eligibility_revision=obligation.eligibility_revision, reason_code="verified_attendance")
    eligibility_workflow.acknowledge(request=_keyed(world.finance, data), obligation_id=obligation.pk, data=data)
    obligation.refresh_from_db()
    payee = obligation.payee_revisions.get(pk=payee_id)
    data = cmd(obligation.version, amount_minor=3000, currency="INR", method="bank_transfer", reference="BANK-RT",
        paid_at=timezone.now(), payee_revision=payee_id, expected_payee_version=payee.version,
        eligibility_revision=obligation.eligibility_revision)
    payout_workflow.record(request=_keyed(world.finance, data), obligation_id=obligation.pk, data=data)
    obligation.refresh_from_db()
    return obligation


def test_claims_awards_decisions_payouts_receipts_and_stage_files_round_trip(make_world, monkeypatch, memory_objects, settings):
    from apps.event_reimbursements.models import (
        ClaimDecision, ClaimLine, GrantAward, GrantRequest, ReimbursementClaim, ReimbursementProgramme,
    )
    from apps.events.staged_forms.response_models import StageFormResponse, StageFormResponseRevision
    from apps.events.staged_forms.upload_models import StageFileCleanup, StageFormAsset
    from apps.payments.event_payouts.attachment_models import FinanceAttachment
    from apps.payments.event_payouts.cleanup_models import FinanceObjectCleanup
    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    from apps.payments.event_payouts.payee_models import EventPayeeRevision
    from apps.payments.event_payouts.payout_models import EventPayoutEntry
    with enabled_encryption():
        world = make_world()
        settings.EVENT_PAYOUT_TENANT_POLICIES = {str(world.space.pk): {"templates": [("IN", "bank_transfer", "in_bank", 1)]}}
        claim, receipt, line_id = submitted(world, monkeypatch)
        obligation = _payout(world, claim, line_id)
        claim.refresh_from_db()
        stage_asset, stage_bytes = _stage_file(world, monkeypatch)
        objects = {receipt.object_key: RECEIPT_BYTES, stage_asset.object_key: stage_bytes}

        def download(_bucket, key, destination, *, versioned):
            data = objects[key]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "version_id": "v1",
                    "content_type": "application/octet-stream"}
        monkeypatch.setattr(backup_storage, "download_object", download)
        monkeypatch.setattr(backup_storage, "assert_object_absent", lambda bucket, key: None)
        source_counts = {model: model.objects.filter(**{path: world.space}).count() for model, path in (
            (ReimbursementClaim, "event__makerspace"), (GrantAward, "request__event__makerspace"),
            (ClaimDecision, "claim__event__makerspace"), (EventPayoutEntry, "obligation__makerspace"),
            (FinanceAttachment, "makerspace"), (StageFormResponseRevision, "response__event__makerspace"))}
        with portable_import_case(world.space, world.owner) as case:
            case.decide_walk_in(world.owner)
            case.decide_walk_in(world.manager)
            records = capture_tenant_objects(case.root, world.space, {"private": "versioned", "public_image": "versioned"})
            assert {receipt.object_key, stage_asset.object_key} <= {row["source_key"] for row in records}
            archive_text = b"".join(path.read_bytes() for path in Path(case.root).rglob("*") if path.is_file())
            assert PAYEE_SECRET.encode() not in archive_text
            case.release_non_regenerable_identities()
            # A target deployment has never seen the source's deployment-custody locators.
            from django.db import transaction
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
                cursor.execute("SET LOCAL session_replication_role = 'replica'")
                cursor.execute("DELETE FROM events_stagefilecleanup")
                cursor.execute("DELETE FROM payments_financeobjectcleanup")
            result = materialize_tenant(case.root, case.job, case.carried, target_identity={"slug": "travel-target"})

        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        assert ReimbursementClaim.objects.filter(event__makerspace=target).count() == source_counts[ReimbursementClaim]
        assert GrantAward.objects.filter(request__event__makerspace=target).count() == source_counts[GrantAward]
        assert ClaimDecision.objects.filter(claim__event__makerspace=target).count() == source_counts[ClaimDecision]
        moved_claim = ReimbursementClaim.objects.get(event__makerspace=target)
        assert moved_claim.uuid == claim.uuid and moved_claim.state == claim.state
        programme = ReimbursementProgramme.objects.get(event__makerspace=target)
        assert (programme.enabled, programme.imported_paused) == (False, True)
        moved = EventPayoutObligation.objects.get(makerspace=target)
        assert moved.approved_minor == obligation.approved_minor == 7000
        assert moved.source_uuid == claim.uuid
        assert EventPayoutEntry.objects.filter(obligation=moved).count() == source_counts[EventPayoutEntry]
        assert sum(EventPayoutEntry.objects.filter(obligation=moved).values_list("amount_minor", flat=True)) == 3000
        decision = ClaimDecision.objects.get(claim=moved_claim)
        assert decision.core_obligation_id == moved.pk
        summary = json.loads(moved.current_revision.decision_summary)
        moved_receipt = FinanceAttachment.objects.get(makerspace=target)
        assert summary["lines"][0]["receipt"]["attachment_id"] == moved_receipt.pk
        assert ClaimLine.objects.get(revision__claim=moved_claim).finance_asset_id == moved_receipt.pk
        assert memory_objects["private"][moved_receipt.object_key] == RECEIPT_BYTES
        assert FinanceObjectCleanup.objects.filter(asset_id=moved_receipt.pk, object_key=moved_receipt.object_key).exists()
        payee = EventPayeeRevision.objects.get(obligation=moved)
        with connection.cursor() as cursor:
            cursor.execute("SELECT details FROM payments_eventpayeerevision WHERE id=%s", [payee.pk])
            raw = cursor.fetchone()[0]
        assert raw.startswith("pii:gcm:v1:") and PAYEE_SECRET not in raw
        assert PAYEE_SECRET in json.dumps(payee.details) if isinstance(payee.details, dict) else PAYEE_SECRET in payee.details
        moved_asset = StageFormAsset.objects.get(event__makerspace=target)
        assert moved_asset.state == "attached" and moved_asset.sha256 == stage_asset.sha256
        assert memory_objects["private"][moved_asset.object_key] == stage_bytes
        assert StageFileCleanup.objects.filter(source_asset_id=moved_asset.pk).exists()
        response = StageFormResponse.objects.get(event__makerspace=target)
        answers = json.loads(response.answers_snapshot)
        assert answers["answers"][0]["value"][0]["asset_id"] == moved_asset.pk
        revision = StageFormResponseRevision.objects.get(response=response)
        assert json.loads(revision.answers_snapshot)["answers"][0]["value"][0]["asset_id"] == moved_asset.pk
        assert response.assignment.imported_paused is True
        assert GrantRequest.objects.get(event__makerspace=target).registration.event.makerspace_id == target.pk
