"""Print subjects and foreign photo sources are declared before any row lock."""
from django.utils.translation import gettext
from contextlib import contextmanager
from dataclasses import dataclass

from apps.events.credentials.boundary import event_command
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.credentials.scopes import registrations
from apps.events.event_permissions import CHECK_IN
from apps.events.profile_photos.models import EventMemberPresentation
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_profiles import MemberProfile


def selections(event_id, member_ids):
    return tuple(EventMemberPresentation.objects.filter(event_id=event_id, member_id__in=member_ids)
        .order_by("pk").values_list("pk", "version", "selected_profile_id", "selected_membership_id"))


@dataclass(frozen=True)
class PrintScope:
    registrations: object
    selections: tuple
    profiles: tuple

    @property
    def account_ids(self):
        return self.registrations.account_ids

    @property
    def tenant_ids(self):
        return tuple(sorted({row[2] for row in self.profiles}))

    def revalidate(self, event):
        self.registrations.revalidate(event)
        current = selections(event.pk, self.account_ids)
        profiles = tuple(MemberProfile.objects.filter(pk__in=[row[0] for row in self.profiles])
            .order_by("pk").values_list("pk", "membership_id", "membership__makerspace_id"))
        if current != self.selections or profiles != self.profiles:
            raise ProgrammeConflict(gettext("Print source changed. Retry preparation."), code="photo_source_changed")


def prepare_scope(event_id, registration_ids):
    scope = registrations(event_id, registration_ids, prepare_names=True)
    selected = selections(event_id, scope.account_ids)
    profiles = tuple(MemberProfile.objects.filter(pk__in=[row[2] for row in selected if row[2]])
        .order_by("pk").values_list("pk", "membership_id", "membership__makerspace_id"))
    return PrintScope(scope, selected, profiles)


@contextmanager
def print_command(job, *, actor):
    scope = prepare_scope(job.event_id, job.registration_ids)
    with event_command(job.event_id, actor=actor, permission=CHECK_IN,
            tenant_ids=scope.tenant_ids, account_ids=scope.account_ids,
            revalidate=scope.revalidate) as (event, actor):
        list(MakerspaceMembership.objects.select_for_update().filter(
            pk__in=[row[1] for row in scope.profiles]).order_by("pk"))
        list(MemberProfile.objects.select_for_update().filter(
            pk__in=[row[0] for row in scope.profiles]).order_by("pk"))
        scope.revalidate(event)
        yield event, actor, scope.registrations
