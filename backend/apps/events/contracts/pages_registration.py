"""Backend pages adapter with independent effective-page publication checks."""

from django.http import Http404

from apps.events.models_event import Event
from apps.events.models_website import EventPageSection
from apps.events.website_visibility import visible_page
from apps.events.website_content import group_enabled
from apps.events.programme_sections.providers import Section, KINDS, validate_options
from .photo_registration import public_member_card

GROUPS = {"prizes": "SPONSORS", "judges": "SPEAKERS", "mentors": "SPEAKERS",
          "project_gallery": "HIGHLIGHTS", "results": "HIGHLIGHTS"}
_providers = {}


def register(*, kind, validator, provider):
    if kind not in KINDS or kind in _providers:
        raise ValueError("Unknown or duplicate programme page section.")
    _providers[kind] = (validator, provider)


class PagesProvider:
    def require_released_section(self, *, event_id, section_id, request_context):
        from apps.events.judging.ports import runtime
        event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
        if event is None:
            raise Http404
        runtime().require_public_origin(event, request_context)
        page = visible_page(event)
        if page is None:
            raise Http404
        row = EventPageSection.objects.filter(pk=section_id, page=page, visibility="published").first()
        if row is None or row.kind not in KINDS or not group_enabled(page, GROUPS[row.kind]):
            raise Http404
        options = validate_options(row.options)
        return Section(id=row.pk, event_id=event.pk, kind=row.kind, options=options)

    def role_cards(self, *, event_id, role):
        from apps.events.contributions.models_roles import EventRoleAssignment
        rows = EventRoleAssignment.objects.filter(event_id=event_id, role=role,
            state="approved", imported_inert=False, display_on_page=True).order_by("pk")
        return tuple(card for pk in rows.values_list("member_id", flat=True)
                     if (card := public_member_card(event_id=event_id, member_id=pk, scope=role)))


def project_sections(*, event_id, request_context):
    """Website projection calls this alongside its ordinary curated sections."""
    event = Event.objects.select_related("makerspace").get(pk=event_id)
    page = visible_page(event)
    if page is None:
        return []
    result = []
    for row in page.sections.filter(kind__in=tuple(_providers), visibility="published").order_by("position", "pk"):
        if not group_enabled(page, GROUPS[row.kind]):
            continue
        _, provider = _providers[row.kind]
        try:
            result.append(provider(event_id=event_id, section_id=row.pk, request_context=request_context))
        except Http404:
            continue
    return result


def install():
    from apps.events.programme_sections.providers import install as install_sections
    install_sections(PagesProvider(), register)
