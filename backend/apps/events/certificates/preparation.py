"""Recipient decryption, key unwrapping and layout capture precede Event locks."""
from dataclasses import dataclass, field
from copy import deepcopy
import json

from django.conf import settings
from django.db import connection
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.encryption.crypto import encrypt, is_envelope
from apps.encryption.mappers import ScopedPiiModelMixin
from apps.encryption.services import get_or_create_active_dek
from apps.encryption.models import MakerspaceEncryptionKey
from apps.events.certificate_templates import issuance_layout
from apps.events.models_certificates import EventAttendanceCertificate as Certificate
from apps.events.models_certificate_templates import EventCertificateTemplateRevision
from apps.events.models_event import Event
from apps.events.models_registration import EventRegistration
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.credentials.errors import ProgrammeConflict
from apps.makerspaces.platform import feature_enabled


def role_recipient(member):
    name = member.display_name or member.get_full_name() or member.username
    identity = json.dumps([member.display_name, member.first_name, member.last_name, member.username], separators=(",", ":"))
    return name, identity


def subject_model(kind):
    if kind == "registration":
        return EventRegistration
    if kind == "role_assignment":
        return EventRoleAssignment
    raise NotFound()


@dataclass(frozen=True)
class PreparedRecipient:
    kind: str
    subject_id: int
    member_id: int
    name: str = field(repr=False)
    raw_name: str = field(repr=False)
    certificate_id: int | None
    envelope: str = field(repr=False)


@dataclass(frozen=True)
class IssuancePreparation:
    event_id: int
    event_version: int
    template_id: int | None
    layout: dict = field(repr=False)
    recipients: tuple = field(repr=False)
    key_version: int | None = None

    @property
    def account_ids(self):
        return tuple(sorted({item.member_id for item in self.recipients}))

    def recipient(self, kind, pk):
        for item in self.recipients:
            if (item.kind, item.subject_id) == (kind, pk):
                return item
        raise ProgrammeConflict("Prepare every certificate subject before locking.", code="subject_changed")

    def revalidate(self, event):
        if self.key_version is not None and not MakerspaceEncryptionKey.objects.filter(
                makerspace_id=event.makerspace_id, version=self.key_version, status="active").exists():
            raise ProgrammeConflict("Certificate key changed. Retry preparation.", code="subject_changed")
        template = selected_template(event)
        if (event.pk != self.event_id or event.version != self.event_version
                or (template.pk if template else None) != self.template_id
                or issuance_layout(template) != self.layout):
            raise ProgrammeConflict("Certificate source changed. Retry preparation.", code="subject_changed")
        for item in self.recipients:
            row = subject_model(item.kind).objects.filter(pk=item.subject_id, event=event).first()
            if row is None or row.member_id != item.member_id:
                raise ProgrammeConflict("Certificate ownership changed.", code="subject_changed")
            raw = row.__dict__["name"] if item.kind == "registration" else role_recipient(User.objects.get(pk=row.member_id))[1]
            if raw != item.raw_name:
                raise ProgrammeConflict("Recipient name changed. Retry preparation.", code="subject_changed")


def selected_template(event):
    if feature_enabled(event.makerspace, "events.certificate_designer"):
        return EventCertificateTemplateRevision.objects.filter(event=event).select_related("artwork").first()
    return None


def prepare_issuance(event_id, subjects, *, for_issue=True):
    if connection.in_atomic_block:
        raise RuntimeError("Prepare certificate recipients outside domain transactions.")
    event = Event.objects.select_related("makerspace").get(pk=event_id)
    template = selected_template(event)
    active = get_or_create_active_dek(event.makerspace_id) if for_issue and settings.PII_ENCRYPTION_ENABLED else None
    recipients = []
    for kind, pk in sorted({(item["subject_kind"], item["subject_id"]) for item in subjects}):
        source = subject_model(kind).objects.filter(pk=pk, event_id=event_id).first()
        if source is None or not source.member_id:
            raise NotFound()
        if kind == "registration":
            raw, name = source.__dict__["name"], source.name
        else:
            name, raw = role_recipient(User.objects.get(pk=source.member_id))
        candidate = Certificate()
        if for_issue:
            candidate._reserve_pk()  # Sequence allocation has no domain row lock.
        envelope = encrypt(name.encode(), active.dek, key_version=active.key.version,
            makerspace_id=event.makerspace_id, table=Certificate._meta.db_table,
            pk=candidate.pk, field="recipient_name") if active and name else name
        recipients.append(PreparedRecipient(kind, pk, source.member_id, name, raw, candidate.pk, envelope))
    return IssuancePreparation(event_id, event.version, template.pk if template else None,
                               deepcopy(issuance_layout(template)), tuple(recipients),
                               active.key.version if active else None)


def save_prepared(row, recipient):
    """Insert only pre-encrypted PII; never invoke the mixin's lazy key path.

    The new row is validated normally. Model.save's legacy ``if self.pk`` update
    branch cannot accept sequence IDs reserved by preparation, so insert through
    its mapped parent after validation. PostgreSQL still checks the issuance shape.
    """
    if recipient.certificate_id is None or (settings.PII_ENCRYPTION_ENABLED
            and recipient.name and not is_envelope(recipient.envelope)):
        raise RuntimeError("Use a recipient prepared for encrypted issuance.")
    row.pk = recipient.certificate_id
    row.full_clean(validate_unique=False, validate_constraints=False)
    row.__dict__["_pii_plain_values"] = {"recipient_name": recipient.name}
    row.__dict__["_pii_original_plain_values"] = {"recipient_name": recipient.name}
    row.__dict__["_pii_raw_values"] = {"recipient_name": recipient.envelope}
    ScopedPiiModelMixin.save(row, force_insert=True)
