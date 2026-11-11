"""Reimbursement, finance payout and staged-form rows for the scoped-PII leak sweep.

One real journey per item (request -> award -> attended claim -> decision -> payee -> paid,
plus a validated stage-form file) builds every parent row through the real services with
scoped PII encryption enabled. The sentinel is then written into the swept field:

* mutable rows (requests, awards, claims, stage assignments/responses/assets) are updated
  through the ORM, as the generic sweep does;
* append-only rows are written at INSERT, cloned from the journey's own row (or built from
  its parents when the journey leaves none), because their history guards refuse updates.

Every write runs inside the tenant's prepared keys, the same pattern as the programme rows.
"""
from contextlib import contextmanager
from uuid import uuid4

from django.apps import apps
from django.db import models
from django.utils import timezone

PREFIXES = ("event_reimbursements.", "payments.EventPayee", "payments.EventPayoutObligationRevision",
            "payments.FinanceAttachment", "payments.PayoutHold", "payments.ReceiptAllocationOverride",
            "events.StageForm")
MUTABLE = {"event_reimbursements.GrantRequest", "event_reimbursements.GrantAward",
           "event_reimbursements.ReimbursementClaim", "events.StageFormAssignment", "events.StageFormResponse",
           "events.StageFormAsset"}


def covers(label):
    return label.startswith(PREFIXES)


def world(request):
    """The full journey, with scoped encryption on for every domain write after setup."""
    settings = request.getfixturevalue("settings")
    monkeypatch = request.getfixturevalue("monkeypatch")
    # make_world pins plaintext mode (and a blank search key) when it is set up; the sweep
    # needs enabled mode with the search key the active SearchKeyGeneration was bound to.
    search = settings.PII_SEARCH_HASH_KEY
    make_world = request.getfixturevalue("make_world")
    w = make_world(hackathon=False)
    settings.PII_ENCRYPTION_ENABLED = True
    settings.PII_SEARCH_HASH_KEY = search
    from apps.encryption.cache import dek_cache
    dek_cache.clear()
    from tests.event_reimbursements.helpers import submitted
    from tests.tenant_migration.test_reimbursement_roundtrip import _payout, _stage_file
    w.claim, w.receipt, w.line_id = submitted(w, monkeypatch)
    w.obligation = _payout(w, w.claim, w.line_id)
    w.stage_asset, _ = _stage_file(w, monkeypatch)
    return w


@contextmanager
def prepared(w):
    from apps.encryption.preparation import prepare_tenants
    with prepare_tenants((w.space.pk,)):
        yield


def model(label):
    return apps.get_model(label)


def latest(label):
    """The journey's newest ``label`` row; each sweep item runs on its own freshly flushed (transactional) database."""
    return model(label).objects.order_by("-pk").first()


def value_for(base, field, token):
    current = base.__dict__.get(field) if base is not None else None
    return {"sweep": token} if isinstance(current, (dict, list)) else token


def _unique_groups(meta):
    groups = [(f.name,) for f in meta.concrete_fields if f.unique and not f.primary_key]
    groups += [tuple(c.fields) for c in meta.constraints if isinstance(c, models.UniqueConstraint) and c.fields]
    return groups


def clone(base, field, value, **overrides):
    """Insert a copy of ``base`` holding ``value``; fresh identities keep unique keys distinct."""
    meta = base._meta
    # Read through the mapper: copied ciphertext would stay bound to the source row's AAD.
    data = {f.attname: getattr(base, f.attname) for f in meta.concrete_fields if not f.primary_key}
    data.update(overrides)
    data[field] = value
    if isinstance(meta.pk, models.UUIDField):
        data[meta.pk.attname] = uuid4()
    for group in _unique_groups(meta):
        if any(meta.get_field(name).attname in overrides for name in group):
            continue
        for name in group:
            target = meta.get_field(name)
            if isinstance(target, models.UUIDField):
                data[target.attname] = uuid4()
                break
            if isinstance(target, models.CharField) and not target.is_relation and len(group) == 1:
                data[target.attname] = f"{data[target.attname]}-sweep-{uuid4().hex[:8]}"
                break
            if isinstance(target, (models.IntegerField, models.PositiveBigIntegerField)) and not target.is_relation:
                others = {meta.get_field(n).attname: data[meta.get_field(n).attname] for n in group if n != name}
                top = type(base).objects.filter(**others).aggregate(models.Max(target.attname))[f"{target.attname}__max"]
                data[target.attname] = (top or 0) + 1
                break
    return type(base).objects.create(**data)


def _decision_clone(w, reason="Base"):
    base = w.claim.decisions.order_by("-sequence").first()
    return clone(base, "reason", reason)


def build(label, field, token, w):
    """Write ``token`` into ``label.field``; returns (row, value written)."""
    now = timezone.now()
    with prepared(w):
        if label in MUTABLE:
            row = latest(label)
            value = value_for(row, field, token)
            setattr(row, field, value)
            row.save(update_fields=[field])
            return row, value
        if label == "event_reimbursements.ClaimAppeal":
            decision = w.claim.decisions.order_by("-sequence").first()
            return model(label).objects.create(claim=w.claim, submitted_by=w.owner, submitted_at=now,
                original_decision=decision, **{field: token}), token
        if label == "event_reimbursements.ClaimScreeningReview":
            return model(label).objects.create(claim=w.claim, revision=w.claim.current_revision, reviewer=w.manager,
                submitted_at=now, recommendation="approve", reason_code="eligible", **{field: token}), token
        if label == "event_reimbursements.ClaimAttendanceAttestation":
            registration = w.claim.award.request.registration
            return model(label).objects.create(claim=w.claim, registration=registration, event=w.event,
                owner_member=w.owner, attendance_revision=registration.attendance_revision, attended_at=now,
                actor=w.manager, reason_code="venue_record", operation_id=uuid4(), **{field: token}), token
        if label == "payments.PayoutHold":
            return model(label).objects.create(obligation=w.obligation, eligibility_revision=w.obligation.eligibility_revision,
                kind="eligibility", action="hold", actor=w.manager, reason_code="review", operation_id=uuid4(),
                **{field: token}), token
        if label == "payments.ReceiptAllocationOverride":
            use = model("payments.ReceiptUse").objects.get(makerspace=w.space, sha256=w.receipt.sha256)
            return model(label).objects.create(receipt_use=use, use_version=use.version, operation_id=uuid4(),
                allocation_snapshot=[], total_minor=0, currency="INR", actor=w.manager, reason_code="manual",
                **{field: token}), token
        if label == "event_reimbursements.ClaimLineDecision":
            base = model(label).objects.filter(decision__claim=w.claim).first()
            return clone(base, field, token, decision_id=_decision_clone(w).pk), token
        if label == "events.StageFormResponseRevision":
            response = w.stage_asset.response
            base = response.submitted_revisions.order_by("-revision").first()
            if base is None:
                return model(label).objects.create(response=response, revision=1, form_revision=response.form_revision,
                    submitted_at=now, submitted_by=w.owner, date_revision=w.event.event_date_revision,
                    **{field: token}), token
            return clone(base, field, token), token
        base = latest(label)
        assert base is not None, f"the journey wrote no {label} row"
        value = value_for(base, field, token)
        overrides = {}
        if label == "payments.EventPayoutObligationRevision":
            overrides["previous_revision_id"] = base.pk  # a later link in the same chain
        if label == "payments.EventPayeeRevision":
            overrides["state"] = "superseded"  # one current payee per obligation
        return clone(base, field, value, **overrides), value


def create(item, token, request):
    w = world(request)
    return build(item.model_label, item.field_name, token, w)
