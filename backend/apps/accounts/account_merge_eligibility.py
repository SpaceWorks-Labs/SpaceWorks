"""Who may merge into whom (decision #65; U-C). Typed refusals and source resolution.

The SURVIVOR is the signed-in person. The SOURCE is an account whose unification
decision was ``converted`` (a former staff account), still a live person, never merged.
Nothing merges on email alone: these predicates only decide eligibility; the proof is
``account_merge_proofs``. A source that cannot merge is indistinguishable at start from
an unknown identifier, so the start answer never enumerates accounts.
"""

import json

from django.db.models import Q
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException

MERGE_NOT_ALLOWED = "merge_not_allowed"
PROOF_FAILED = "proof_failed"
PROOF_EXPIRED = "proof_expired"
FACTOR_ENROLMENT_REQUIRED = "factor_enrolment_required"
TENANT_GATED = "tenant_gated"
ALREADY_MERGED = "already_merged"
PREVIEW_STALE = "preview_stale"
ERROR_CODES = (MERGE_NOT_ALLOWED, PROOF_FAILED, PROOF_EXPIRED, FACTOR_ENROLMENT_REQUIRED,
               TENANT_GATED, ALREADY_MERGED, PREVIEW_STALE)
_STATUS = {PROOF_FAILED: 400, PROOF_EXPIRED: 410, FACTOR_ENROLMENT_REQUIRED: 409, TENANT_GATED: 409,
           ALREADY_MERGED: 409, PREVIEW_STALE: 409, MERGE_NOT_ALLOWED: 403}


class MergeRefused(APIException):
    def __init__(self, code, detail):
        self.status_code = _STATUS[code]
        super().__init__({"code": code, "detail": detail}, code=code)
        self.detail = {"code": code, "detail": detail}


def account_refusal(user):
    """Why ``user`` can take no part in a merge, or ``None``.

    Platform accounts, shells, tenant-dump stubs, walk-ins, a space's anonymous requester,
    deletion-requested, inactive and restricted accounts are all refused.
    """
    from apps.accounts.principal_guards import is_anonymous_requester
    from apps.accounts.staff_identity import is_person

    if user is None or user.pk is None or not is_person(user):
        return "not_a_person"
    if user.is_tenant_dump_stub or user.is_walk_in or is_anonymous_requester(user):
        return "system_account"
    if user.deletion_requested_at is not None or not user.is_active:
        return "inactive"
    if user.access_status != "active" or user.is_superuser:
        return "restricted"
    return None


def require_survivor(user):
    if account_refusal(user) is not None:
        raise MergeRefused(MERGE_NOT_ALLOWED, "This account cannot link another account.")


def converted_record(source):
    from apps.accounts.models_account_merge import AccountMergeRecord

    return AccountMergeRecord.objects.filter(
        source=source, decision=AccountMergeRecord.Decision.CONVERTED).first()


def source_refusal(source, survivor):
    """Why ``source`` cannot merge into ``survivor`` (a refusal code), or ``None``."""
    from apps.accounts.models_account_merge import AccountMergeRecord

    if source is None or survivor is None or source.pk == survivor.pk:
        return MERGE_NOT_ALLOWED
    if getattr(source, "merged_into_id", None) is not None or AccountMergeRecord.objects.filter(
            source=source, decision=AccountMergeRecord.Decision.MERGED,
            state=AccountMergeRecord.State.COMPLETED).exists():
        return ALREADY_MERGED
    if account_refusal(source) is not None or converted_record(source) is None:
        return MERGE_NOT_ALLOWED
    return None


def held_snapshot(source):
    """The converted record's snapshot (original email/name/phone), decrypted, or ``{}``."""
    record = converted_record(source)
    if record is None or record.snapshot_scheme != record.SnapshotScheme.DEPLOYMENT:
        return {}
    from apps.makerspaces.secrets import decrypt_value
    try:
        return json.loads(decrypt_value(record.snapshot_ciphertext))
    except Exception:
        return {}


def source_email(source):
    """Where the source's code goes: its current email, else the address held at conversion."""
    return (source.email or "").strip() or (held_snapshot(source).get("email") or "").strip()


def identifier_digest(identifier):
    """Keyed digest of what the person typed; the identifier itself is never stored."""
    clean = (identifier or "").strip().lower()
    return salted_hmac("spaceworks.accounts.account_merge.identifier", clean, algorithm="sha256").hexdigest()


def resolve_source(identifier, survivor):
    """The eligible source an identifier names (username, email or held email), or ``None``."""
    from apps.accounts.models import User
    from apps.accounts.models_account_merge import AccountMergeRecord

    clean = (identifier or "").strip()
    if not clean or len(clean) > 254:
        return None
    converted = AccountMergeRecord.objects.filter(decision=AccountMergeRecord.Decision.CONVERTED)
    candidates = User.objects.filter(pk__in=converted.values("source_id")).exclude(pk=survivor.pk)
    match = candidates.filter(Q(username__iexact=clean) | Q(email__iexact=clean)).order_by("pk").first()
    if match is None and "@" in clean:
        held = converted.filter(held_fields__contains=["email"]).values_list("source_id", flat=True)
        for user in candidates.filter(pk__in=held).order_by("pk"):
            if (held_snapshot(user).get("email") or "").strip().lower() == clean.lower():
                match = user
                break
    return match if match is not None and source_refusal(match, survivor) is None else None


def merge_suggested(user):
    """Q17 dashboard nudge: a converted account that has not linked another account yet."""
    from apps.accounts.models_account_merge import AccountMergeRecord

    if account_refusal(user) is not None or converted_record(user) is None:
        return False
    return not AccountMergeRecord.objects.filter(target=user, decision=AccountMergeRecord.Decision.MERGED,
                                                 state=AccountMergeRecord.State.COMPLETED).exists()
