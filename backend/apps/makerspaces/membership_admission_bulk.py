"""Bulk approve / reject on the join-request queue (X11).

Behind `membership.admission_tools`, `manage_members` in the request's space. Each request
goes through the SAME single-request services (`approve_request`, `revoke_request`), one
transaction each, so one refused request (expired, already decided, missing vouches)
never blocks or rolls back the others. The outcome per request is returned, and one
`membership.bulk_decided` summary row is audited next to each request's own entries.
"""
from rest_framework.exceptions import APIException

from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.models import MembershipRequest

MAX_BULK = 100


def _code(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict) and detail.get("code"):
        return str(detail["code"])
    return getattr(exc, "default_code", "refused")


def bulk_decide(actor, makerspace, request_ids, *, decision, role=None, reason=""):
    from apps.makerspaces.membership_admission import approve_request
    from apps.makerspaces.membership_revocation import revoke_request
    require_membership_feature(makerspace, "admission_tools")
    ids = list(dict.fromkeys(int(value) for value in request_ids))[:MAX_BULK]
    from apps.accounts import rbac
    from apps.makerspaces.member_unit_scope import narrow_by_unit_lookup
    # Parity O-B1/O-B2: a unit-scoped lead's out-of-scope requests do not exist for them (reported `not_found`).
    visible = narrow_by_unit_lookup(MembershipRequest.objects.filter(makerspace=makerspace, pk__in=ids), actor,
                                    makerspace.pk, "unit_choice__unit__path", rbac.Action.MANAGE_MEMBERS)
    rows = {row.pk: row for row in visible}
    results = []
    for request_id in ids:
        row = rows.get(request_id)
        if row is None:
            results.append({"id": request_id, "ok": False, "code": "not_found"})
            continue
        try:
            if decision == "approve":
                approve_request(actor, row, role)
            else:
                revoke_request(actor, row, reason)
            results.append({"id": request_id, "ok": True, "code": ""})
        except APIException as exc:
            results.append({"id": request_id, "ok": False, "code": _code(exc)})
    done = [item["id"] for item in results if item["ok"]]
    audit.record(actor, "membership.bulk_decided", makerspace=makerspace, target=makerspace,
                 meta={"decision": decision, "request_ids": done,
                       "refused": len(results) - len(done)})
    return results
