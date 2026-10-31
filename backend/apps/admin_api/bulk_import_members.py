"""Member import, part 1: mapping, normalising and planning rows (G18, #128 C-13).

The file is parsed on the server (CSV, TSV or .xlsx through openpyxl, #123) by the same
`rows_from_upload` the inventory import uses. Columns are mapped to `FIELDS` (a guessed
mapping is offered), every row is normalised, and each gets one planned action:

* `create`  -- a new pending membership (invited, or "record only" when staff chose it);
* `update`  -- refreshes a pending row with the same email that has not been accepted;
* `skip`    -- with a reason: missing/invalid email, duplicate in the file (email, phone or
  member number), an active member here already has this email, or an unknown plan.

De-duplication never looks at accounts: an existing account is NEVER linked (C-13). Only
this space's own members (by their email) and pending rows are compared.
"""
import re
from datetime import date, datetime

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

FIELDS = ("name", "email", "phone", "member_number", "plan", "starts_on", "ends_on",
          "state_code", "gstin", "notes", "record_only")
ALIASES = {
    "name": ("name", "full name", "member name"), "email": ("email", "e-mail", "email address"),
    "phone": ("phone", "mobile", "phone number"), "member_number": ("member number", "member no", "membership number", "id"),
    "plan": ("plan", "membership plan", "membership"), "starts_on": ("start", "start date", "starts on", "joined"),
    "ends_on": ("end", "end date", "ends on", "expiry", "valid until"), "state_code": ("state code", "state"),
    "gstin": ("gstin", "gst"), "notes": ("notes", "note", "remarks"), "record_only": ("record only",),
}
_PHONE = re.compile(r"[^\d+]")
PREVIEW_ROWS = 50


def suggest_mapping(headers):
    lowered = {str(header).strip().lower(): header for header in headers}
    mapping = {}
    for field, names in ALIASES.items():
        for name in names:
            if name in lowered and lowered[name] not in mapping.values():
                mapping[field] = lowered[name]
                break
    return mapping


def _text(row, mapping, field):
    column = mapping.get(field)
    value = row.get(column, "") if column else ""
    return "" if value is None else str(value).strip()


def _date(raw):
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue
    raise ValueError(raw)


def normalise(row, mapping):
    email = _text(row, mapping, "email").lower()
    out = {"name": _text(row, mapping, "name")[:200], "email": email,
           "phone": _PHONE.sub("", _text(row, mapping, "phone"))[:32],
           "member_number": _text(row, mapping, "member_number")[:40], "plan": _text(row, mapping, "plan"),
           "state_code": _text(row, mapping, "state_code")[:2], "gstin": _text(row, mapping, "gstin").upper()[:15],
           "notes": _text(row, mapping, "notes")[:4000],
           "record_only": _text(row, mapping, "record_only").lower() in ("yes", "y", "true", "1")}
    errors = []
    try:
        validate_email(email)
    except DjangoValidationError:
        errors.append("email_invalid")
    for field in ("starts_on", "ends_on"):
        try:
            out[field] = _date(_text(row, mapping, field))
        except ValueError:
            out[field], errors = None, [*errors, f"{field}_invalid"]
    if out["starts_on"] and out["ends_on"] and out["ends_on"] <= out["starts_on"]:
        errors.append("dates_out_of_order")
    return out, errors


def plan_rows(makerspace, raw_rows, mapping, *, existing):
    """Normalise and decide every row. `existing` comes from `existing_state(makerspace)`."""
    plans = existing["plans"]
    seen = {"email": set(), "phone": set(), "member_number": set()}
    planned = []
    for index, raw in enumerate(raw_rows, start=2):  # row 1 is the header
        row, errors = normalise(raw, mapping)
        reason = errors[0] if errors else ""
        if not reason and row["plan"] and row["plan"].lower() not in plans:
            reason = "plan_unknown"
        for key in ("email", "phone", "member_number"):
            if not reason and row[key] and row[key] in seen[key]:
                reason = f"duplicate_{key}"
        if not reason and row["email"] in existing["member_emails"]:
            reason = "already_member"
        owner = existing["numbers"].get(row["member_number"]) if row["member_number"] else None
        if not reason and owner is not None and owner != row["email"]:
            reason = "duplicate_member_number"
        for key in seen:
            if row[key]:
                seen[key].add(row[key])
        action = "skip" if reason else ("update" if row["email"] in existing["pending"] else "create")
        planned.append({"row": index, "action": action, "reason": reason, "data": row})
    return planned


def existing_state(makerspace):
    """What de-duplication compares against: this space's members and pending rows."""
    from apps.makerspaces.models import ImportedMember, MakerspaceMembership, MembershipPlan
    member_emails = {(email or "").strip().lower() for email in MakerspaceMembership.objects.filter(
        makerspace=makerspace, status="active").values_list("user__email", flat=True)}
    pending, numbers = {}, {}
    for row in ImportedMember.objects.filter(makerspace=makerspace).exclude(status=ImportedMember.Status.CANCELLED):
        if row.status in (ImportedMember.Status.INVITED, ImportedMember.Status.RECORD_ONLY) and row.email:
            pending[row.email.lower()] = row
        if row.external_number:
            numbers[row.external_number] = (row.email or "").lower()
    plans = {}
    for plan in MembershipPlan.objects.filter(makerspace=makerspace, is_active=True, archived_at__isnull=True):
        plans[plan.name.lower()] = plan
        if plan.slug:
            plans[plan.slug.lower()] = plan
    return {"member_emails": member_emails, "pending": pending, "numbers": numbers, "plans": plans}


def counts(planned):
    totals = {"create": 0, "update": 0, "skip": 0}
    for item in planned:
        totals[item["action"]] += 1
    return totals


def preview_payload(headers, mapping, planned):
    def visible(item):
        data = dict(item["data"])
        for key in ("starts_on", "ends_on"):
            data[key] = data[key].isoformat() if isinstance(data[key], date) else None
        return {**item, "data": data}

    return {"headers": list(headers), "mapping": mapping, "suggested_mapping": suggest_mapping(headers),
            "counts": counts(planned), "rows": [visible(item) for item in planned[:PREVIEW_ROWS]],
            "total_rows": len(planned)}
