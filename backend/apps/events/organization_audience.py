"""Live event audience adapter over always-present organization membership policy."""

from django.db.models import prefetch_related_objects
from rest_framework.exceptions import APIException

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled
from apps.organizations.audience import (
    eligible_accounts, lock_membership_sources, owned_space_ids, usable_spaces,
)
from apps.organizations.models import Organization, OrganizationMakerspace

AUDIENCE = "participating_organizations"
FEATURE = "events.organization_audience"
PROJECTION_FEATURES = (
    "events.invites", "events.ticket_types", "events.promo_codes", FEATURE,
    "events.offline_checkin", "events.broadcasts", "events.website", "events.embed",
    "reports.event_exports", "reports.event_pdf",
)


class OrganizationAudienceRefused(APIException):
    status_code = 403
    default_code = "organization_audience_required"

    def __init__(self, code="organization_audience_required", detail=None):
        super().__init__({"code": code, "detail": detail or "Active membership in a participating organization is required."})


class AudienceChanged(APIException):
    status_code = 409
    default_code = "organization_audience_changed"
    default_detail = "Organization ownership changed. Retry registration."

    def __init__(self):
        super().__init__({"code": self.default_code, "detail": self.default_detail})


def candidate_ids(event):
    organizer_ids = set(event.organizers.values_list("organization_id", flat=True)) if event.pk else set()
    owners = OrganizationMakerspace.objects.filter(makerspace_id=event.makerspace_id, relationship="owner")
    return organizer_ids | set(owners.values_list("organization_id", flat=True))


def candidates(event):
    if not usable_spaces().filter(pk=event.makerspace_id).exists():
        return Organization.objects.none()
    return Organization.objects.filter(pk__in=candidate_ids(event), is_active=True).order_by("name", "pk")


def audience_projection(event):
    return audience_projections([event])[(event._meta.label, event.pk)]


def _projection(rows):
    return {"participating_organizations": rows,
            "audience_label": "Open to members of " + ", ".join(row["name"] for row in rows)
            if rows else "Open to members of participating organizations (none currently available)"}


def audience_projections(events, *, feature_flags=None):
    """Batch public attribution for one response, never cache admission proofs."""
    events = list(events)
    if not events:
        return {}
    host_ids = {event.makerspace_id for event in events}
    hosts = list(usable_spaces().filter(pk__in=host_ids).only("pk", "enabled_modules", "enabled_features"))
    usable_hosts = {host.pk for host in hosts}
    if feature_flags is not None:
        from apps.makerspaces.capability_projection import feature_flags_for_servable
        feature_flags.update({pk: {key: False for key in PROJECTION_FEATURES} for pk in host_ids})
        feature_flags.update({host.pk: feature_flags_for_servable(host, PROJECTION_FEATURES) for host in hosts})
    owners = dict(OrganizationMakerspace.objects.filter(
        makerspace_id__in=usable_hosts, relationship="owner",
    ).values_list("makerspace_id", "organization_id"))
    # .all() reads the prefetch cache; .values_list() would issue one query per event.
    # Group by model because series and occurrences have different organizer relations.
    by_model = {}
    for event in events:
        if event.pk and event.makerspace_id in usable_hosts:
            by_model.setdefault(type(event), []).append(event)
    for rows in by_model.values():
        prefetch_related_objects(rows, "organizers")
    ids_by_event = {}
    for event in events:
        ids = set()
        if event.makerspace_id in usable_hosts:
            if event.pk:
                ids.update(row.organization_id for row in event.organizers.all())
            if event.makerspace_id in owners:
                ids.add(owners[event.makerspace_id])
        ids_by_event[(event._meta.label, event.pk)] = ids
    organization_ids = set().union(*ids_by_event.values())
    organizations = list(Organization.objects.filter(
        pk__in=organization_ids, is_active=True,
    ).order_by("name", "pk").values("id", "name"))
    return {
        key: _projection([row for row in organizations if row["id"] in ids])
        for key, ids in ids_by_event.items()
    }


def lock_admission_sources(event, user_ids=(), *, extra_space_ids=(), include_authority=False):
    """Event lock first; acquire ALL contributing spaces before the host module lock.

    The venue owner may change while obtaining the spaces. Refuse and retry the outer
    transaction if discovery changed; never acquire a new lower-PK space out of order.
    Organizer writers hold the event lock, owner writers hold the relevant space lock.
    """
    if event.registration_audience != AUDIENCE:
        return
    organization_ids = candidate_ids(event)
    space_ids = owned_space_ids(organization_ids) | {event.makerspace_id} | set(extra_space_ids)
    list(Makerspace.objects.select_for_update().filter(pk__in=space_ids).order_by("pk"))
    if candidate_ids(event) != organization_ids or not owned_space_ids(organization_ids).issubset(space_ids):
        raise AudienceChanged()
    lock_ids = organization_ids
    if include_authority:
        from .staff_grant_locks import authority_sources
        lock_ids = organization_ids | authority_sources(event)[3]
    lock_membership_sources(lock_ids, set(user_ids) - {None}, space_ids)
    if candidate_ids(event) != organization_ids or not owned_space_ids(organization_ids).issubset(space_ids):
        raise AudienceChanged()
    event.makerspace = Makerspace.objects.get(pk=event.makerspace_id)


def require_organization_audience(event, member):
    if event.registration_audience != AUDIENCE:
        return
    if not feature_enabled(event.makerspace, FEATURE):
        raise OrganizationAudienceRefused("organization_audience_disabled", "Organization audience is disabled.")
    if event.organization_admission_blocked:
        raise OrganizationAudienceRefused("organization_audience_not_ready", "Staff must reconfigure the imported organization audience.")
    if not usable_spaces().filter(pk=event.makerspace_id).exists():
        raise OrganizationAudienceRefused()
    if not member or not getattr(member, "is_authenticated", False) or not member.pk:
        raise OrganizationAudienceRefused()
    if not eligible_accounts(candidate_ids(event)).filter(pk=member.pk).exists():
        raise OrganizationAudienceRefused()


def eligible_event_accounts(event):
    if (event.organization_admission_blocked or not feature_enabled(event.makerspace, FEATURE)
            or not usable_spaces().filter(pk=event.makerspace_id).exists()):
        return User.objects.none()
    return eligible_accounts(candidate_ids(event))


def annotate_roster_eligibility(event, rows):
    """One account query for the entire page; never persist a changing proof."""
    ids = {row.member_id for row in rows}
    eligible = set(eligible_event_accounts(event).filter(pk__in=ids).values_list("pk", flat=True)) if event.registration_audience == AUDIENCE else ids
    for row in rows:
        row.no_longer_eligible = row.member_id not in eligible


def require_queued_admission(event, registration):
    """Call after the batch source fence, before any queue or money mutation."""
    require_organization_audience(event, registration.member)
    if event.registration_audience == AUDIENCE:
        from .host_waivers import require_host_waiver
        require_host_waiver(event, registration.member, registration=registration)
