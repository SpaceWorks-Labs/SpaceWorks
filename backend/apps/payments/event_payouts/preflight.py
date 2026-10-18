"""Canonical, nonlocking fact port. A cached eligible projection is insufficient.

G installs an always-present retained-data reader. It must only READ canonical
rows while the host/obligation locks are held, never lock an Event or R parent.
Canonical writers take that same host lock before changing eligibility.
"""
from dataclasses import dataclass, replace
from .decision_snapshots import eligibility
from .validation import closed, PayoutValidationError

FLAGS = ("participation_eligible", "attendance_eligible", "project_eligible", "event_active", "owner_active")
_provider = None


@dataclass(frozen=True)
class Facts:
    evidence: dict
    participation_eligible: bool
    attendance_eligible: bool
    project_eligible: bool
    event_active: bool
    owner_active: bool
    retained_only: bool = False

    def __post_init__(self):
        eligibility(self.evidence)
        if any(type(getattr(self, flag)) is not bool for flag in (*FLAGS, "retained_only")):
            raise PayoutValidationError("invalid_eligibility_facts")

    @property
    def eligible(self):
        return all(getattr(self, flag) for flag in FLAGS)

    def as_dict(self):
        return {"evidence": dict(self.evidence), **{flag: getattr(self, flag) for flag in (*FLAGS, "retained_only")}}

    @classmethod
    def from_dict(cls, value):
        closed(value, ("evidence", *FLAGS), ("retained_only",))
        return cls(**value)


def install(provider):
    global _provider
    if _provider is not None and _provider is not provider:
        raise RuntimeError("Payout preflight provider already installed.")
    _provider = provider


def resolve_locked(obligation):
    from .errors import require
    if obligation.domain_coordination_state == "detached":
        # No Events/R lookup is permitted after a real module purge. The purge
        # adapter must preserve the last full acknowledged fact, not just IDs.
        return replace(Facts.from_dict(obligation.eligibility_evidence), retained_only=True)
    require(_provider is not None, "payout_preflight_unavailable", status=503)
    facts = _provider.read(obligation=obligation)
    require(isinstance(facts, Facts), "payout_preflight_unavailable", status=503)
    return facts


def require_fresh_locked(obligation, *, expected_revision):
    from .eligibility_workflow import active_holds
    from .errors import require
    facts = resolve_locked(obligation)
    require(expected_revision == obligation.eligibility_revision, "eligibility_changed")
    require(facts.as_dict() == obligation.eligibility_evidence, "eligibility_changed")
    if facts.retained_only:
        require(obligation.eligibility_history.filter(evidence_revision=obligation.eligibility_revision,
            acknowledged_at__isnull=False).exists(), "eligibility_acknowledgement_required")
    require(facts.eligible and obligation.eligibility_status == "eligible"
        and not obligation.hold_reason_code and not active_holds(obligation).exists(), "payout_held")
    return facts
