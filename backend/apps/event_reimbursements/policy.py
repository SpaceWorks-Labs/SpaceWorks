"""Closed, deterministic finance policy. No geocoding or exchange-rate I/O."""
from decimal import Decimal, InvalidOperation
import re
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.validation import minor

CATEGORIES = ("rail", "air", "bus", "ground_transport", "lodging")
VENUE_SOURCES = ("qr", "venue_station", "offline_sync")
POLICY_FIELDS = frozenset({"enabled", "request_phase", "request_opens_at", "request_closes_at",
    "award_mode", "tier_rules", "allowed_categories", "exclusions", "min_distance_km",
    "eligible_countries", "eligible_cohorts", "award_accept_days", "claim_due_at", "attendance_required",
    "require_project_submission", "permitted_venue_sources", "category_limits", "min_application_stage",
    "required_submission", "required_submission_stage"})


def identifiers(value, pattern, maximum=250):
    require(isinstance(value, list) and len(value) <= maximum and all(isinstance(v, str)
        and re.fullmatch(pattern, v) for v in value), "invalid_policy_identifiers", status=400)
    require(len(value) == len(set(value)), "duplicate_policy_identifiers", status=400)
    return sorted(value)


def rules(value, mode):
    require(isinstance(value, dict) and len(value) <= 100, "invalid_tier_rules", status=400)
    if mode == "percentage":
        require(set(value) == {"basis_points", "cap_minor"} and type(value["basis_points"]) is int
                and 0 <= value["basis_points"] <= 10000, "invalid_percentage", status=400)
        minor(value["cap_minor"], zero=True)
    elif mode in ("fixed_tier", "route_cap"):
        require(bool(value), "award_tier_required", status=400)
        priorities = set()
        for key, rule in value.items():
            require(isinstance(key, str) and re.fullmatch(r"[a-z0-9_-]{1,64}", key)
                and isinstance(rule, dict), "invalid_tier_rules", status=400)
            allowed = {"amount_minor"} if mode == "fixed_tier" else {
                "amount_minor", "priority", "origin_country", "destination_country", "region", "mode"}
            require(not set(rule) - allowed and "amount_minor" in rule, "invalid_tier_rules", status=400)
            minor(rule["amount_minor"], zero=True)
            if mode == "route_cap":
                priority = rule.get("priority")
                require(type(priority) is int and 0 <= priority <= 10000 and priority not in priorities,
                        "invalid_route_priority", status=400)
                priorities.add(priority)
                for name in ("origin_country", "destination_country"):
                    if name in rule:
                        require(isinstance(rule[name], str) and re.fullmatch(r"[A-Z]{2}", rule[name]),
                                "invalid_route_country", status=400)
                if "region" in rule:
                    require(isinstance(rule["region"], str) and re.fullmatch(r"[A-Z0-9_-]{1,32}", rule["region"]),
                            "invalid_route_region", status=400)
                require("mode" not in rule or rule["mode"] in ("rail", "air", "bus", "car", "other"),
                        "invalid_route_mode", status=400)
    else:
        require(not set(value) - {"cap_minor"}, "invalid_tier_rules", status=400)
        if value:
            minor(value["cap_minor"], zero=True)
    return value


def validate_policy(value, *, event):
    require(isinstance(value, dict) and not set(value) - POLICY_FIELDS, "invalid_programme_settings", status=400)
    value = dict(value)
    require(value.get("request_phase", "both") in ("application", "after_acceptance", "both"), "invalid_request_phase", status=400)
    mode = value.get("award_mode", "need_based")
    require(mode in ("fixed_tier", "route_cap", "percentage", "need_based"), "invalid_award_mode", status=400)
    for key in ("enabled", "attendance_required", "require_project_submission"):
        require(key not in value or type(value[key]) is bool, "invalid_programme_settings", status=400)
    for key in ("request_opens_at", "request_closes_at", "claim_due_at"):
        if value.get(key) is not None:
            from datetime import datetime
            from django.utils.timezone import is_aware
            require(isinstance(value[key], datetime) and is_aware(value[key]), "invalid_policy_datetime", status=400)
            from datetime import timezone
            value[key] = value[key].astimezone(timezone.utc)
    if "claim_due_at" in value:
        require(value["claim_due_at"] is not None and value["claim_due_at"] > event.ends_at,
                "claim_due_before_event_end", status=400)
    if value.get("request_opens_at") and value.get("request_closes_at"):
        require(value["request_closes_at"] > value["request_opens_at"], "invalid_request_window", status=400)
    if "award_accept_days" in value:
        require(type(value["award_accept_days"]) is int and 1 <= value["award_accept_days"] <= 365,
                "invalid_award_accept_days", status=400)
    if value.get("min_distance_km") is not None:
        try:
            distance = Decimal(str(value["min_distance_km"]))
        except (InvalidOperation, ValueError):
            distance = Decimal("NaN")
        require(distance.is_finite() and 0 <= distance <= 40075 and distance.as_tuple().exponent >= -3,
                "invalid_distance", status=400)
        value["min_distance_km"] = distance.quantize(Decimal("0.001"))
    if "allowed_categories" in value:
        value["allowed_categories"] = identifiers(value["allowed_categories"], "|".join(CATEGORIES), 5)
        require(bool(value["allowed_categories"]), "invalid_categories", status=400)
        value["allowed_categories"] = [category for category in CATEGORIES if category in value["allowed_categories"]]
    if "exclusions" in value:
        value["exclusions"] = identifiers(value["exclusions"], r"[a-z][a-z0-9_]{0,31}", 30)
        require(set(value["exclusions"]) <= set(CATEGORIES) | {"meals", "visa", "insurance", "baggage", "upgrades", "fees"},
                "invalid_exclusions", status=400)
    if "eligible_countries" in value:
        value["eligible_countries"] = identifiers(value["eligible_countries"], r"[A-Z]{2}")
        from apps.forms_schema.profile_fields import COUNTRY_CODES
        require(set(value["eligible_countries"]) <= COUNTRY_CODES, "invalid_country", status=400)
    if "eligible_cohorts" in value:
        value["eligible_cohorts"] = identifiers(value["eligible_cohorts"], r"[1-9][0-9]{0,18}")
        if value["eligible_cohorts"]:
            from apps.events.models import HackathonApplicationCohort
            require(HackathonApplicationCohort.objects.filter(event=event, pk__in=value["eligible_cohorts"]).count()
                == len(value["eligible_cohorts"]), "invalid_cohort", status=400)
    if "permitted_venue_sources" in value:
        value["permitted_venue_sources"] = identifiers(value["permitted_venue_sources"], "|".join(VENUE_SOURCES), 3)
    limits = value.get("category_limits", {})
    require(isinstance(limits, dict) and not set(limits) - set(CATEGORIES), "invalid_category_limits", status=400)
    for limit in limits.values():
        minor(limit, zero=True)
    if "tier_rules" in value:
        rules(value["tier_rules"], mode)
    _required_submission(value, event)
    if value.get("require_project_submission"):
        from apps.events.models import HackathonConfig
        require(HackathonConfig.objects.filter(event=event, enabled=True).exists(), "project_requirement_hackathon_only", status=400)
    return value


def _required_submission(value, event):
    """G11: ``required_submission`` and its legacy yes/no mirror ``require_project_submission`` agree."""
    from .config_models import REQUIRED_SUBMISSION
    if "required_submission" in value:
        mode = value["required_submission"]
        require(mode in REQUIRED_SUBMISSION, "invalid_required_submission", status=400)
        position = value.get("required_submission_stage")
        if mode in ("stage", "shortlisted_at"):
            from apps.events.submissions.models_stages import SubmissionStage
            stage = SubmissionStage.objects.filter(event=event, position=position).first() if type(position) is int else None
            require(stage is not None and (mode == "stage" or stage.shortlist_after), "invalid_required_submission_stage",
                    status=400)
        else:
            value["required_submission_stage"] = None
        value["require_project_submission"] = mode != "none"
    elif "require_project_submission" in value:  # A client that only knows the old switch.
        value["required_submission"] = "any_stage" if value["require_project_submission"] else "none"
        value["required_submission_stage"] = None
