"""Who must have a design approved, and who may approve it (#128 C-28, #136, Q-I12).

Most specific setting wins: event -> programme -> organisation -> space. Defaults: the
membership group (member cards and ID programmes) requires approval for anyone who
cannot approve; the event group requires none (#128), unless an event, its
organisation or the space turns it on. Approval itself always sits with the host
space's approvers (`APPROVE_CARD_DESIGNS`, held by the Space Manager).
"""
from apps.accounts import rbac

from .models import CardApprovalSetting, CardDesign

MEMBERSHIP_DOMAINS = (CardDesign.Domain.MEMBER_CARDS, CardDesign.Domain.ID_PROGRAMME, CardDesign.Domain.STAFF_CARDS)
DEFAULTS = {CardApprovalSetting.Group.MEMBERSHIP: True, CardApprovalSetting.Group.EVENT: False}


def group_for(domain):
    return CardApprovalSetting.Group.MEMBERSHIP if domain in MEMBERSHIP_DOMAINS else CardApprovalSetting.Group.EVENT


def _event_organization_id(design):
    if design.organization_id:
        return design.organization_id
    if not design.event_id:
        return None
    return event_organization_id(design.event_id)


def required_for(design):
    group = group_for(design.domain)
    rows = CardApprovalSetting.objects.filter(makerspace_id=design.makerspace_id, group=group)
    candidates = []
    if design.event_id:
        candidates.append(rows.filter(event_id=design.event_id))
    if design.programme_id:
        candidates.append(rows.filter(programme_id=design.programme_id))
        organization_id = design.programme.organization_id
    else:
        organization_id = _event_organization_id(design)
    if organization_id:
        candidates.append(rows.filter(organization_id=organization_id))
    candidates.append(rows.filter(organization__isnull=True, programme__isnull=True, event__isnull=True))
    for queryset in candidates:
        value = queryset.values_list("required", flat=True).first()
        if value is not None:
            return value
    return DEFAULTS[group]


def inherited(makerspace_id, group, organization_id=None):
    """What a programme or event level falls back to: its organisation, then the space, then the default."""
    rows = CardApprovalSetting.objects.filter(makerspace_id=makerspace_id, group=group)
    if organization_id:
        value = rows.filter(organization_id=organization_id).values_list("required", flat=True).first()
        if value is not None:
            return value
    value = rows.filter(organization__isnull=True, programme__isnull=True, event__isnull=True).values_list(
        "required", flat=True).first()
    return DEFAULTS[group] if value is None else value


def event_organization_id(event_id):
    from apps.events.models import EventOrganizer
    return EventOrganizer.objects.filter(event_id=event_id).order_by("pk").values_list(
        "organization_id", flat=True).first()


def can_approve(actor, design):
    return rbac.can(actor, rbac.Action.APPROVE_CARD_DESIGNS, design.makerspace_id)


def needs_approval(actor, design):
    return required_for(design) and not can_approve(actor, design)


def level_value(makerspace, group, *, organization=None, programme=None, event=None):
    """The value set at exactly this level, or None when the level inherits."""
    return CardApprovalSetting.objects.filter(
        makerspace=makerspace, group=group, organization=organization, programme=programme, event=event,
    ).values_list("required", flat=True).first()


def set_level(actor, makerspace, group, required, *, organization=None, programme=None, event=None):
    """Write one level (#136). `required=None` clears it, so the level inherits again."""
    from apps.audit import services as audit
    level = "event" if event else "programme" if programme else "organisation" if organization else "space"
    scope = {"makerspace": makerspace, "group": group, "organization": organization, "programme": programme,
             "event": event}
    if required is None:
        row = CardApprovalSetting.objects.filter(**scope).first()
        if row is None:
            return None
        row.delete()
        audit.record(actor, "card_design.approval_setting_changed", makerspace=makerspace, target=makerspace,
                     meta={"group": group, "level": level, "required": None})
        return None
    row, _ = CardApprovalSetting.objects.update_or_create(**scope, defaults={"required": bool(required)})
    audit.record(actor, "card_design.approval_setting_changed", makerspace=makerspace, target=row,
                 meta={"group": group, "level": level, "required": bool(required)})
    return row
