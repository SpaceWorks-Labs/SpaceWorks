"""Line/date validation and category ceilings against the accepted offer policy."""
from decimal import Decimal
from django.utils import timezone
from apps.payments.event_payouts.errors import require


def validate_line(line, *, event, award):
    from zoneinfo import ZoneInfo
    local = ZoneInfo(event.timezone_name)
    rules = award.calculation_snapshot
    allowed = rules.get("allowed_categories", ("rail", "air", "bus", "ground_transport", "lodging"))
    require(line["category"] in allowed and line["category"] not in rules.get("exclusions", ()),
            "claim_category_ineligible", status=400)
    require(line["expense_date"] <= timezone.now().astimezone(local).date() and line["rate_date"] == line["expense_date"],
            "invalid_expense_date", status=400)
    require(Decimal(line["fx_rate"]) > 0, "invalid_fx_rate", status=400)
    require(line["original_currency"] != award.currency or Decimal(line["fx_rate"]) == 1,
            "same_currency_fx_invalid", status=400)
    route = line["route"]
    require(isinstance(route, dict) and not set(route) - {"origin", "destination", "mode"}, "invalid_claim_route", status=400)
    if line["category"] != "lodging":
        require(set(route) == {"origin", "destination", "mode"} and all(isinstance(route[key], str)
            and 1 <= len(route[key]) <= 500 for key in ("origin", "destination")), "claim_route_required", status=400)
        expected = {"rail": ("rail",), "air": ("air",), "bus": ("bus",), "ground_transport": ("car", "bus", "other")}
        require(route["mode"] in expected[line["category"]], "invalid_claim_route", status=400)
        require(not any(line.get(k) is not None for k in ("lodging_starts_on", "lodging_ends_on", "lodging_nights")),
                "lodging_fields_not_allowed", status=400)
    else:
        start, end, nights = (line.get(key) for key in ("lodging_starts_on", "lodging_ends_on", "lodging_nights"))
        require(start is not None and end is not None and nights is not None and (end - start).days == nights
            and start <= event.ends_at.astimezone(local).date() and end >= event.starts_at.astimezone(local).date(),
                "invalid_lodging_dates", status=400)
        require(not route, "invalid_claim_route", status=400)


def validate_decisions(*, lines, decisions, award, outcome):
    by_id = {str(row.line_uuid): row for row in lines}
    require(len(decisions) == len(by_id) and len({str(row["line_uuid"]) for row in decisions}) == len(by_id)
        and {str(row["line_uuid"]) for row in decisions} == set(by_id), "line_decisions_incomplete", status=400)
    totals, approved = {}, 0
    for item in decisions:
        line = by_id[str(item["line_uuid"])]
        amount = item["approved_minor"]
        require(type(amount) is int and 0 <= amount <= line.converted_minor, "line_approval_out_of_bounds", status=400)
        require(amount == line.converted_minor or bool(item["reason_code"]), "line_reason_required", status=400)
        totals[line.category] = totals.get(line.category, 0) + amount
        approved += amount
    caps = award.calculation_snapshot.get("category_caps", {})
    require(all(amount <= caps.get(category, amount) for category, amount in totals.items()), "category_cap_exceeded")
    claimed = sum(row.converted_minor for row in lines)
    require(approved <= award.amount_minor, "award_cap_exceeded")
    expected = "rejected" if approved == 0 else "approved" if approved == claimed else "partially_approved"
    require(outcome == expected, "decision_outcome_mismatch", status=400)
    return approved
