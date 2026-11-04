"""Who must have a design approved, and who may approve it (#128 C-28, #136, Q-I12).

Most specific setting wins: event -> programme -> organisation -> space. Defaults: the
membership group (member cards and ID programmes) requires approval for anyone who
cannot approve; the event group requires none (#128), unless an event, its
organisation or the space turns it on. Approval itself always sits with the host
space's approvers (`APPROVE_CARD_DESIGNS`, held by the Space Manager).
"""
from apps.accounts import rbac

from .models import CardApprovalSetting, CardDesign

MEMBERSHIP_DOMAINS = (CardDesign.Domain.MEMBER_CARDS, CardDesign.Domain.ID_PROGRAMME)
DEFAULTS = {CardApprovalSetting.Group.MEMBERSHIP: True, CardApprovalSetting.Group.EVENT: False}


def group_for(domain):
    return CardApprovalSetting.Group.MEMBERSHIP if domain in MEMBERSHIP_DOMAINS else CardApprovalSetting.Group.EVENT


def _event_organization_id(design):
    if design.organization_id:
        return design.organization_id
    if not design.event_id:
        return None
    from apps.events.models import EventOrganizer
    row = EventOrganizer.objects.filter(event_id=design.event_id).order_by("pk").values_list(
        "organization_id", flat=True).first()
    return row


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


def can_approve(actor, design):
    return rbac.can(actor, rbac.Action.APPROVE_CARD_DESIGNS, design.makerspace_id)


def needs_approval(actor, design):
    return required_for(design) and not can_approve(actor, design)


def set_level(actor, makerspace, group, required, *, organization=None, programme=None, event=None):
    from apps.audit import services as audit
    row, _ = CardApprovalSetting.objects.update_or_create(
        makerspace=makerspace, group=group, organization=organization, programme=programme, event=event,
        defaults={"required": bool(required)})
    level = "event" if event else "programme" if programme else "organisation" if organization else "space"
    audit.record(actor, "card_design.approval_setting_changed", makerspace=makerspace, target=row,
                 meta={"group": group, "level": level, "required": bool(required)})
    return row
