"""Discover subjects before fences and reject scope changes after the Event lock."""
from dataclasses import dataclass, field

from apps.transaction_guards import in_domain_transaction
from rest_framework.exceptions import NotFound

from apps.events.models_registration import EventRegistration
from .errors import ProgrammeConflict


@dataclass(frozen=True)
class RegistrationScope:
    event_id: int
    identities: tuple
    names: dict = field(default_factory=dict, repr=False)
    raw_names: dict = field(default_factory=dict, repr=False)

    @property
    def account_ids(self):
        return tuple(sorted({member for _, member in self.identities if member}))

    def revalidate(self, event):
        actual = tuple(EventRegistration.objects.filter(event_id=event.pk,
            pk__in=[pk for pk, _ in self.identities]).order_by("pk").values_list("pk", "member_id"))
        if event.pk != self.event_id or actual != self.identities:
            raise ProgrammeConflict("Registration ownership changed. Retry the command.", code="subject_changed")

    def bind(self, row):
        if (row.pk, row.member_id) not in self.identities or row.event_id != self.event_id:
            raise ProgrammeConflict("Registration ownership changed.", code="subject_changed")
        if row.pk in self.names:
            if any(row.__dict__[key] != value for key, value in self.raw_names[row.pk].items()):
                raise ProgrammeConflict("Badge text changed. Retry preparation.", code="print_snapshot_changed")
            row.__dict__.setdefault("_pii_plain_values", {}).update(self.names[row.pk])
        return row


def registrations(event_id, ids, *, prepare_names=False):
    if prepare_names and in_domain_transaction():
        raise RuntimeError("Prepare recipient names outside the event transaction.")
    rows = list(EventRegistration.objects.filter(event_id=event_id, pk__in=ids).order_by("pk"))
    if len(rows) != len(set(ids)):
        raise NotFound()
    return RegistrationScope(event_id, tuple((row.pk, row.member_id) for row in rows),
        {row.pk: {key: getattr(row, key) for key in ("name", "email", "phone")} for row in rows} if prepare_names else {},
        {row.pk: {key: row.__dict__[key] for key in ("name", "email", "phone")} for row in rows} if prepare_names else {})
