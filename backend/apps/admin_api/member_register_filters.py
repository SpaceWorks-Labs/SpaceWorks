"""Parity O-B2: ONE filter contract for the member register, the roster and the card-job resolver.

Every screen that selects members by filter goes through `apply_member_filters`, so "the members this chip shows"
is the same set everywhere (the register table, the roster, "print cards for everyone matching", bulk actions).

Contract (every key optional; an unknown VALUE is ignored like the roster's other optional filters, an unknown KEY
is refused by `clean_params`):

    q                      name / username / email contains, or a member number (``TNK-0042``, ``42``, ``#42``)
    chip                   one standing chip, see CHIPS
    plan                   plan id with a live term            role / standing / joined_after / joined_before
    staff / verified / minor / volunteer = true|false          waiver_needed = true
    title                  member title id (any assignment)    unit   unit id; the unit and everything beneath it
    status                 membership status (default "active" where a caller applies it)

`standing` keeps its roster meaning (account access: active | restricted | suspended); the register's term
standings are the `chip` values. Unit scope (O-B1) is applied here whenever `actor` is passed, so a scoped lead can
never widen the set with a filter.
"""
import re

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac

# Term-derived chips (computed like the register's `standing` column) and request-derived chips.
# `active` includes a term ending within 30 days (the register shows that one as `ending_soon`).
TERM_CHIPS = {"active": ("active", "ending_soon"), "expiring": ("ending_soon",), "grace": ("grace",),
              "lapsed": ("lapsed",), "upcoming": ("upcoming",), "no_term": ("no_term",)}
TERM_STANDINGS = {value for values in TERM_CHIPS.values() for value in values}
REQUEST_CHIPS = {"approval": ("requested", "awaiting_vouches"), "payment": ("awaiting_payment",),
                 "changes": ("changes_requested",)}
CHIPS = (*TERM_CHIPS, *REQUEST_CHIPS)
# The register's historical `standing=` values, accepted as chip aliases.
LEGACY_STANDINGS = {"ending_soon": "expiring"}
PARAMS = ("q", "role", "standing", "joined_after", "joined_before", "plan", "staff", "verified", "minor",
          "volunteer", "waiver_needed", "status", "title", "unit", "chip")
_NUMBER = re.compile(r"(\d{1,9})\s*$")


def clean_params(raw):
    """-> {key: str} of the documented, non-empty keys. Raises 400 for a key outside the contract."""
    unknown = set(raw) - set(PARAMS)
    if unknown:
        raise ValidationError({"filter": gettext("Unknown filter: {names}.").format(names=", ".join(sorted(unknown)))})
    return {key: str(value) for key, value in raw.items() if value not in (None, "")}


def from_query(query_params):
    """The contract keys out of a request's query string (other keys -- paging, ordering -- are not ours)."""
    return {key: query_params.get(key) for key in PARAMS if query_params.get(key) not in (None, "")}


def chip_from_params(params):
    """`chip`; an unknown chip is a 400."""
    chip = params.get("chip")
    if chip is not None and chip not in CHIPS:
        raise ValidationError({"chip": gettext("Use one of: {value}.").format(value=", ".join(CHIPS))})
    return chip


def register_params(query_params):
    """The register's contract: as `from_query`, but its historical `standing=ending_soon|grace|...` (a TERM
    standing, unlike the roster's account standing) is read as the matching chip."""
    params = from_query(query_params)
    legacy = query_params.get("standing")
    if legacy in (TERM_STANDINGS | set(LEGACY_STANDINGS)) and "chip" not in params:
        params.pop("standing", None)
        params["chip"] = LEGACY_STANDINGS.get(legacy, legacy)
    elif legacy is not None and "chip" not in params and legacy not in ("restricted", "suspended"):
        raise ValidationError({"standing": gettext("Use one of: {value}.").format(
            value=", ".join(sorted(TERM_STANDINGS | set(LEGACY_STANDINGS))))})
    return params


def term_chip_member_ids(space, chip, now=None):
    from apps.operations.reports_membership_l4_lists import _latest_terms, _standing
    now, wanted = now or timezone.now(), TERM_CHIPS[chip]
    from apps.makerspaces.models import MakerspaceMembership
    latest = _latest_terms(space)
    ids = MakerspaceMembership.objects.filter(makerspace=space).values_list("pk", flat=True)
    return [pk for pk in ids if _standing(latest.get(pk), now) in wanted]


def _search(queryset, term):
    query = (Q(user__username__icontains=term) | Q(user__first_name__icontains=term)
             | Q(user__last_name__icontains=term) | Q(user__email__icontains=term))
    number = _NUMBER.search(term)
    if number:
        query |= Q(member_number=int(number.group(1)))
    return queryset.filter(query)


def apply_member_filters(queryset, params, space, *, actor=None, action=rbac.Action.MANAGE_MEMBERS, now=None):
    """Narrow a `MakerspaceMembership` queryset (already tenant-scoped) by the contract in `params`."""
    from apps.admin_api.roster_filters import apply_roster_filters
    from apps.admin_api.views_member_memberships import _more_roster_filters
    from apps.makerspaces.member_unit_scope import narrow_memberships
    from apps.makerspaces.membership_features import membership_feature_on
    from apps.makerspaces.models import MembershipRequest
    from apps.makerspaces.models_member_units import MemberUnit
    if actor is not None:
        queryset = narrow_memberships(queryset, actor, space.pk, action)
    if term := (params.get("q") or "").strip():
        queryset = _search(queryset, term)
    rest = {key: value for key, value in params.items() if key != "q"}
    queryset = apply_roster_filters(_more_roster_filters(queryset, rest), rest, space)
    if params.get("status"):
        queryset = queryset.filter(status=params["status"])
    if str(params.get("title", "")).isdigit():
        queryset = queryset.filter(title_assignments__title_id=int(params["title"]))
    if str(params.get("unit", "")).isdigit() and membership_feature_on(space, "units"):
        unit = MemberUnit.objects.filter(makerspace=space, pk=int(params["unit"])).first()
        queryset = (queryset.filter(unit_assignment__unit__path__startswith=unit.path) if unit is not None
                    else queryset.none())
    chip = chip_from_params(params)
    if chip in TERM_CHIPS:
        queryset = queryset.filter(pk__in=term_chip_member_ids(space, chip, now))
    elif chip in REQUEST_CHIPS:
        queryset = queryset.filter(Exists(MembershipRequest.objects.filter(
            makerspace=space, user=OuterRef("user"), state__in=REQUEST_CHIPS[chip])))
    return queryset
