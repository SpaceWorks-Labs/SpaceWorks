"""Parity O-B2: bulk actions on members chosen in the member register.

    assign_title   -- add one member title (optionally as the primary one)            `membership.titles`
    move_unit      -- put the members in one unit (or take them out of any unit)      `membership.units`
    send_reminder  -- the renewal reminder, once per member per day                    `membership.renewal_desk`
    issue_cards    -- issue a member card to members who hold none                     manage_member_cards
    email_cards    -- email the live card to its holder (the card-email limits apply)  manage_member_cards

Convention (the same as `membership_admission_bulk`): per-row results, never all-or-nothing. Every row runs the
EXISTING single-member service in its own transaction, so one refusal (out of scope, already reminded, no card,
quota reached) never blocks or rolls back the others, and every row keeps the audit entry its service writes. One
`membership.register_bulk_applied` summary row (counts only) is audited next to them.

Selection is either explicit `membership_ids` or a `filter` (the shared contract of
`admin_api.member_register_filters`); a filter that matches more than MAX_ROWS rows is refused (400), never
silently truncated. Unit scope (O-B1) narrows both: a member outside the actor's unit is reported `not_found`.
"""
from django.db import transaction
from django.http import Http404
from django.utils.translation import gettext
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.member_unit_scope import narrow_memberships
from apps.makerspaces.membership_admission_settings import AdmissionError
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.models import MakerspaceMembership

MAX_ROWS = 200
MANAGE, CARDS = rbac.Action.MANAGE_MEMBERS, rbac.Action.MANAGE_MEMBER_CARDS
#: action -> (membership.* switch that gates it or None, RBAC action it needs)
ACTIONS = {
    "assign_title": ("titles", MANAGE), "move_unit": ("units", MANAGE), "send_reminder": ("renewal_desk", MANAGE),
    "issue_cards": (None, CARDS), "email_cards": (None, CARDS),
}


def _code(exc):
    if isinstance(exc, Http404):
        return "not_found"
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict) and detail.get("code"):
        return str(detail["code"])
    return str(getattr(exc, "default_code", "refused"))


def select_ids(actor, space, action, membership_ids=None, filter_params=None):
    """-> the ordered ids to act on (at most MAX_ROWS). Out-of-scope ids stay in the list and report not_found."""
    if (membership_ids is None) == (filter_params is None):
        raise ValidationError({"detail": gettext("Send either membership_ids or filter.")})
    if membership_ids is not None:
        return list(dict.fromkeys(int(value) for value in membership_ids))[:MAX_ROWS]
    from apps.admin_api.member_register_filters import apply_member_filters, clean_params
    queryset = rbac.scope_by_action(actor, action, MakerspaceMembership.objects.filter(makerspace=space))
    matched = list(apply_member_filters(queryset, clean_params(filter_params), space, actor=actor, action=action)
                   .order_by("pk").values_list("pk", flat=True)[:MAX_ROWS + 1])
    if len(matched) > MAX_ROWS:
        raise ValidationError({"filter": gettext("The filter matches more than {count} members; narrow it.").format(
            count=MAX_ROWS)})
    return matched


def _visible(actor, space, action, ids):
    rows = rbac.scope_by_action(actor, action, MakerspaceMembership.objects.select_related("user", "makerspace")
                                .filter(makerspace=space, pk__in=ids))
    return {row.pk: row for row in narrow_memberships(rows, actor, space.pk, action)}


def _do_assign_title(actor, row, options):
    from apps.makerspaces.membership_titles import assign
    from apps.makerspaces.models import MembershipTitle
    title = MembershipTitle.objects.filter(makerspace_id=row.makerspace_id, pk=options["title_id"]).first()
    if title is None:
        raise ValidationError({"title_id": gettext("Choose a current title of this makerspace.")})
    assign(actor, row, title, primary=bool(options.get("primary")))


def _do_move_unit(actor, row, options):
    from apps.makerspaces.member_unit_assign import assign_member_unit
    assign_member_unit(actor, row, options.get("unit_id"), action=MANAGE)


def _do_send_reminder(actor, row, options):
    from apps.makerspaces.membership_renewal_desk import send_reminders
    if not send_reminders(actor, row.makerspace, [row.pk])["sent"]:
        raise AdmissionError("not_due", gettext("Not due for a reminder today."))


def _do_issue_cards(actor, row, options):
    from apps.makerspaces.member_card_services import issue_card
    issue_card(actor, row)


def _do_email_cards(actor, row, options):
    from apps.card_designs.email import send_card_email
    from apps.makerspaces.models import MemberCard
    card = MemberCard.objects.filter(membership=row, revoked_at__isnull=True).first()
    if card is None:
        raise AdmissionError("no_card", gettext("This member holds no card."))
    if not send_card_email("member_card", card, actor=actor):
        raise AdmissionError("not_sent", gettext("The card email was not sent (limit or rule)."))


RUNNERS = {"assign_title": _do_assign_title, "move_unit": _do_move_unit, "send_reminder": _do_send_reminder,
           "issue_cards": _do_issue_cards, "email_cards": _do_email_cards}


def check_options(action, options):
    """Fail before any row runs when the action's own parameters are unusable."""
    if action == "assign_title" and not isinstance(options.get("title_id"), int):
        raise ValidationError({"title_id": gettext("Choose a title.")})
    if action == "move_unit" and options.get("unit_id") is not None and not isinstance(options.get("unit_id"), int):
        raise ValidationError({"unit_id": gettext("Choose a unit, or send null to remove the unit.")})


def apply_bulk(actor, space, action, *, membership_ids=None, filter_params=None, options=None):
    """-> [{"id", "ok", "code"}] in request order."""
    if action not in ACTIONS:
        raise ValidationError({"action": gettext("Unknown bulk action.")})
    options = options or {}
    switch, needed = ACTIONS[action]
    require_membership_feature(space, "register_bulk")
    if switch:
        require_membership_feature(space, switch)
    if not rbac.can(actor, needed, space.pk):
        raise PermissionDenied()
    check_options(action, options)
    ids = select_ids(actor, space, needed, membership_ids, filter_params)
    visible = _visible(actor, space, needed, ids)
    results = []
    for membership_id in ids:
        row = visible.get(membership_id)
        if row is None:
            results.append({"id": membership_id, "ok": False, "code": "not_found"})
            continue
        try:
            with transaction.atomic():
                RUNNERS[action](actor, row, options)
            results.append({"id": membership_id, "ok": True, "code": ""})
        except (APIException, Http404) as exc:
            results.append({"id": membership_id, "ok": False, "code": _code(exc)})
    applied = sum(item["ok"] for item in results)
    audit.record(actor, "membership.register_bulk_applied", makerspace=space, target=space,
                 meta={"bulk_action": action, "rows": len(results), "applied": applied,
                       "refused": len(results) - applied})
    return results
