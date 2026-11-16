"""Real database fixtures; no workflow, permission, key or ledger doubles."""
import base64
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from cryptography.fernet import Fernet
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts import reauthentication
from apps.encryption.cache import dek_cache
from apps.events.models import Event, EventRegistration, HackathonConfig
from apps.makerspaces.models import Makerspace
from apps.event_reimbursements import programme_workflow
from apps.event_reimbursements.config_models import ReimbursementProgramme
from apps.event_reimbursements.budget_models import ReimbursementBudgetPool
from tests.accounts.account_factories import make_staff
from tests.accounts.test_reauthentication import request as session_request, PASSWORD


def keyed(request, data):
    """Core finance commands bind the Idempotency-Key header to the body's operation_id."""
    request.META["HTTP_IDEMPOTENCY_KEY"] = str(data["operation_id"])
    request.__dict__.pop("headers", None)
    return request


def cmd(version=0, **kwargs):
    return {"operation_id": uuid4(), "expected_version": version, **kwargs}


@pytest.fixture
def make_world(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    settings.PII_KEY_BROKER = "local"
    settings.PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.PII_SEARCH_HASH_KEY = ""
    settings.EVENT_PAYOUT_ENABLED_TEMPLATES = (("IN", "cash"), ("IN", "bank_transfer"))
    # Hackathon admission issues event credentials; give the world its own test keys.
    settings.EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = 1
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {"1": base64.b64encode(b"r" * 32).decode()}
    settings.EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = base64.b64encode(b"d" * 32).decode()
    dek_cache.clear()
    def build(*, hackathon=False, total=1000000, policy=None):
        suffix = uuid4().hex[:10]
        space = Makerspace.objects.create(name="Travel support", slug="travel-" + suffix)
        settings.EVENT_PAYOUT_TENANT_POLICIES = {**getattr(settings, "EVENT_PAYOUT_TENANT_POLICIES", {}),
            str(space.pk): {"templates": [("IN", "cash", "cash", 1), ("IN", "bank_transfer", "in_bank", 1)]}}
        # Notifications are deliberately off: domain deadlines and core money
        # remain usable without channels, the rail or membership.
        space.enabled_modules = ["events", "event_reimbursements", "request_workflow"]
        # Account-only registration is an opt-in Events capability.
        space.enabled_features = list(set(space.enabled_features) | {"events.account_registration", "events.hackathons"})
        space.save(update_fields=["enabled_modules", "enabled_features"])
        with transaction.atomic():
            manager = make_staff(space, username="finance-" + suffix, password=PASSWORD)
        owner = User.objects.create_user(username="maker-" + suffix, account_kind="member", password=PASSWORD,
            email="maker-" + suffix + "@example.test", phone="+919876543210", email_verified_at=timezone.now())
        start = timezone.now() + timedelta(days=3)
        event = Event.objects.create(makerspace=space, title="Hackathon" if hackathon else "Ordinary workshop",
            starts_at=start, ends_at=start + timedelta(days=1), status="published", is_public=True,
            location="Workshop", location_kind="indoor", registration_audience="accounts")
        if hackathon:
            HackathonConfig.objects.create(event=event, enabled=True, review_mode="auto", team_mode="solo",
                application_form={"schema_version": 2, "form_id": "application", "revision": 1, "questions": []})
        finance = session_request(manager)
        reauthentication.verify(finance, password=PASSWORD)
        creation = programme_workflow.create_or_get(request=finance, event_id=event.pk,
            data=cmd(currency="INR", initial_total_minor=total, initial_settings=policy or {}))
        programme = ReimbursementProgramme.objects.get(pk=creation["id"])
        pool = ReimbursementBudgetPool.objects.get(pk=creation["pool_id"])
        programme_workflow.configure(request=finance, event_id=event.pk, data=cmd(programme.version,
            policy_revision=programme.finance_policy_revision, settings={"enabled": True}, pool_id=pool.pk,
            expected_pool_version=pool.version, budget_delta_minor=0, reason_code="approved"))
        programme.refresh_from_db(); pool.refresh_from_db()
        return SimpleNamespace(space=space, manager=manager, owner=owner, event=event, programme=programme,
            pool=pool, finance=finance, member_session=session_request(owner, surface="member"), hackathon=hackathon)
    yield build
    dek_cache.clear()


@pytest.fixture
def world(make_world):
    return make_world()
