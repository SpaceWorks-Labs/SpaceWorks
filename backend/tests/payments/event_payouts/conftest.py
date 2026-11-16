"""PostgreSQL fixtures exercise real core workflows and mandatory encryption."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
import pytest
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.reauthentication import stamp
from apps.encryption.account_write_fence import account_fences
from apps.encryption.cache import dek_cache
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.events.models import Event
from apps.makerspaces.models import Makerspace
from apps.payments.event_payouts import preflight
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from apps.payments.event_payouts.cleanup_models import FinanceObjectCleanup
from apps.payments.event_payouts.decision_workflow import create_locked
from apps.payments.event_payouts.receipt_models import ReceiptUse, ReceiptAllocation
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from tests.accounts.test_reauthentication import request as browser_request
from tests.return_helpers import make_member

C = json.loads((Path(__file__).resolve().parents[2] / "events/programme/contracts/reimbursement_addon.json").read_text())


def request_for(actor, data, *, reauth=True):
    request = browser_request(actor)
    request.META["HTTP_IDEMPOTENCY_KEY"] = str(data["operation_id"])
    if reauth:
        stamp(request)
    return request


@contextmanager
def domain_boundary(bundle):
    key = prepare_tenant_key(bundle.space.pk)
    accounts = tuple(sorted((bundle.actor.pk, bundle.owner.pk)))
    with boundary_tenant_write(bundle.space.pk), tenant_key_context(key), transaction.atomic(), account_fences(accounts, (bundle.space.pk,)):
        Event.objects.select_for_update().get(pk=bundle.event.pk)
        Makerspace.objects.select_for_update().get(pk=bundle.space.pk)
        yield


@pytest.fixture
def finance_bundle(settings, monkeypatch):
    settings.PII_ENCRYPTION_ENABLED = False
    settings.PII_KEY_BROKER = "local"
    settings.PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.PII_SEARCH_HASH_KEY = ""
    settings.AWS_STORAGE_BUCKET_NAME = "private-test"
    dek_cache.clear()
    space = Makerspace.objects.create(name="Core finance", slug="core-finance", enabled_modules=["request_workflow", "staff_admin"])
    actor = make_member("payout-manager", space)
    owner = User.objects.create_user(username="payout-owner", account_kind="member", email="owner@example.test")
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Ordinary event", starts_at=now - timedelta(days=3), ends_at=now - timedelta(days=2))
    summary = deepcopy(C["core_evidence"]["decision_summary"])
    summary["decision"]["actor_id"] = actor.pk
    summary["eligibility"]["registration_id"] = None
    summary["eligibility"]["checkin_event_id"] = None
    summary["eligibility"]["correction_watermark"] = None
    asset = FinanceAttachment.objects.create(makerspace=space, event=event, event_id_snapshot=event.pk,
        event_title_snapshot=event.title, owner_member=owner, purpose="reimbursement_receipt", binding_kind="claim",
        binding_uuid=UUID(summary["source"]["claim_uuid"]), question_id="receipt", state="attached", generation=1,
        expected_bytes=10, actual_bytes=10, declared_mime="application/pdf", canonical_mime="application/pdf",
        sha256="a" * 64, original_filename="private receipt.pdf", staging_key="finance/staging/fixture", object_key="finance/final/fixture",
        scan_status="skipped", scanner_policy="none", scanner_version="policy-none-v1", attached_at=now,
        retention_policy_revision=1, retention_days_snapshot=2555)
    use = ReceiptUse.objects.create(makerspace=space, sha256=asset.sha256, original_currency="INR", declared_total_minor=175000)
    ReceiptAllocation.objects.create(receipt_use=use, use_version=1, claim_uuid=asset.binding_uuid,
        line_uuid=UUID(summary["lines"][0]["line_uuid"]), amount_minor=175000)
    receipt = summary["lines"][0]["receipt"]
    receipt.update(attachment_id=asset.pk, receipt_use_id=use.pk)
    FinanceObjectCleanup.objects.create(source_makerspace_id=space.pk, asset_id=asset.pk, bucket="private-test",
        staging_key=asset.staging_key, object_key=asset.object_key)
    bundle = SimpleNamespace(space=space, actor=actor, owner=owner, event=event, snapshot=summary, asset=asset)
    with domain_boundary(bundle):
        bundle.obligation = create_locked(makerspace=space, event=event, owner=owner, actor=actor,
            operation_id=uuid4(), decision_summary=summary)
    bundle.facts = preflight.Facts(summary["eligibility"], True, True, True, True, True)
    monkeypatch.setattr(preflight, "_provider", SimpleNamespace(read=lambda **kwargs: bundle.facts))
    yield bundle
    dek_cache.clear()
