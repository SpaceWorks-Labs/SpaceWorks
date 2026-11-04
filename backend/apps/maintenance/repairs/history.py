"""One call per issue step: the append-only timeline row AND the audit entry together."""

from apps.audit import services as audit


def step(issue, kind, actor, action, *, contact=None, note="", occurred_on=None, amount=None, currency="",
         meta=None):
    from apps.maintenance.models import IssueEvent
    event = IssueEvent.objects.create(issue=issue, kind=kind, actor=actor, contact=contact,
                                      note=str(note or "")[:4000], occurred_on=occurred_on, amount=amount,
                                      currency=(currency or "").lower()[:3])
    audit.record(actor, action, makerspace=issue.makerspace, target=issue, meta={
        "issue_id": issue.pk, "area": issue.area, "state": issue.state, **(meta or {})})
    return event


def lock(issue):
    from apps.maintenance.models import IssueReport
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(issue.makerspace_id)
    # Only the non-null makerspace join: FOR UPDATE refuses the nullable side of an outer join.
    return IssueReport.objects.select_for_update().select_related("makerspace").get(pk=issue.pk)
