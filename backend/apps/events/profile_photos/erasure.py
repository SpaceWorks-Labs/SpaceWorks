"""Account erasure drops only unsubmitted sources and withdraws presentation consent."""
from django.utils.translation import gettext
from dataclasses import dataclass

from django.db.models import Q

from apps.encryption.account_write_fence import assert_account_fence_held
from apps.events.credentials.errors import ProgrammeConflict


@dataclass(frozen=True)
class ErasureScope:
    events: tuple
    tenant_ids: tuple


class EventSubjectErasure:
    @staticmethod
    def discover(user_id):
        from apps.events.answer_derivations.models import EventAnswerDerivation
        from apps.events.models_event import Event
        from apps.makerspaces.models_profiles import MemberProfile
        from .models import EventMemberPresentation
        answers = EventAnswerDerivation.objects.filter(Q(registration__member_id=user_id)
            | Q(application__member_id=user_id) | Q(role_assignment__member_id=user_id))
        ids = set(answers.values_list("event_id", flat=True))
        ids.update(EventMemberPresentation.objects.filter(member_id=user_id).values_list("event_id", flat=True))
        events = tuple(Event.objects.filter(pk__in=ids).order_by("pk").values_list("pk", "makerspace_id", "series_id"))
        tenants = {row[1] for row in events}
        tenants.update(MemberProfile.objects.filter(event_presentations__member_id=user_id)
                       .values_list("membership__makerspace_id", flat=True))
        return ErasureScope(events, tuple(sorted(tenants)))

    @staticmethod
    def erase_locked(user_id, prepared, *, actor):
        from apps.events.models_event import Event
        from apps.events.models_series import EventSeries
        from apps.makerspaces.models import Makerspace
        from apps.events.answer_derivations.workflow import erase_owner_drafts_locked
        from apps.events.contracts.providers import LockedContext
        from .models import EventMemberPresentation
        from .source_lifecycle import clear_selections

        assert_account_fence_held(user_id, exclusive=True)
        if EventSubjectErasure.discover(user_id) != prepared:
            raise ProgrammeConflict(gettext("Erasure subjects changed. Retry the entire erasure."), code="subject_changed")
        list(EventSeries.objects.select_for_update().filter(
            pk__in={row[2] for row in prepared.events if row[2]}).order_by("pk"))
        events = list(Event.objects.select_for_update().filter(pk__in=[row[0] for row in prepared.events]).order_by("pk"))
        if tuple((row.pk, row.makerspace_id, row.series_id) for row in events) != prepared.events:
            raise ProgrammeConflict(gettext("Erasure subjects changed."), code="subject_changed")
        list(Makerspace.objects.select_for_update().filter(pk__in=prepared.tenant_ids).order_by("pk"))
        for event in events:
            locks = LockedContext(event_id=event.pk, tenant_ids=prepared.tenant_ids, account_ids=(user_id,))
            erase_owner_drafts_locked(owner_member_id=user_id, event_id=event.pk,
                                     locks=locks, actor_id=actor.pk if actor else None)
        clear_selections(EventMemberPresentation.objects.filter(member_id=user_id).filter(
            Q(selected_profile__isnull=False) | Q(selected_membership__isnull=False)), actor=actor)
