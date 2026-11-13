"""Model-free provider signatures, not registry entries or HTTP authorization."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Mapping, Protocol
from uuid import UUID

from .subjects import AnswerSubject, StageResponseSubject


class ReadPurpose(StrEnum):
    TEAM_ORIGINAL = "team_original"
    OWNER_HISTORY = "owner_history"
    APPLICATION_REVIEW = "application_review"
    JUDGE_SUBMISSION = "judge_submission"
    ORGANIZER_ASSET = "organizer_asset"
    SPONSOR_TRACK = "sponsor_track"
    SPONSOR_RESUME = "sponsor_resume"
    HELP_ATTACHMENT = "help_attachment"
    PUBLIC_GALLERY = "public_gallery"
    PUBLIC_MEMBER_PHOTO = "public_member_photo"
    SAVED_RESUME = "saved_resume"
    SAVED_DETAILS_EXPORT = "saved_details_export"
    PERSONAL_DATA_EXPORT = "personal_data_export"
    CERTIFICATE_PDF = "certificate_pdf"
    BADGE_PDF = "badge_pdf"
    PRINT_RESOURCE = "print_resource"
    TEMPLATE_ARTWORK = "template_artwork"
    PROVIDER_PDF = "provider_pdf"
    FINANCE_REIMBURSEMENT_RECEIPT = "finance_reimbursement_receipt"
    FINANCE_PAYEE_DOCUMENT = "finance_payee_document"


@dataclass(frozen=True, kw_only=True)
class LockedContext:
    """Proof supplied by the workflow, never deserialized from HTTP input."""

    event_id: int
    tenant_ids: tuple[int, ...]
    account_ids: tuple[int, ...]


@dataclass(frozen=True, kw_only=True)
class PreparedIntent:
    """Opaque encrypted preparation; hide ciphertext and key bindings in repr."""

    intent_id: UUID
    operation_id: UUID
    subject: AnswerSubject | StageResponseSubject
    ciphertext: bytes = field(repr=False)
    key_version: int = field(repr=False)
    key_epoch: int = field(repr=False)
    canonical_answer_sha256: str
    form_sha256: str
    expires_at: datetime


@dataclass(frozen=True, kw_only=True)
class PhotoSelection:
    profile_id: int | None
    membership_id: int | None
    source_revision: str | None
    print_photo_consent: bool = False
    public_card_consent: bool = False
    public_card_scopes: tuple[str, ...] = ()


class SavedDetailPreparation(Protocol):
    def prepare_saved_detail_intent(
        self, *, actor_id: int, subject: AnswerSubject | StageResponseSubject, validated_form: object,
        choices: Mapping[str, bool], base_versions: Mapping[str, int], operation_id: UUID,
        outer_operation_id: UUID | None = None, form_slot: str | None = None,
    ) -> PreparedIntent | None:
        """Outside domain transactions; no true choices means no vault intent."""
        ...

    def insert_prepared_locked(
        self, prepared: PreparedIntent, *, subject: AnswerSubject | StageResponseSubject, locks: LockedContext,
    ) -> UUID:
        """Recheck deadline/epoch/owner/form/hash under predeclared fences; no KMS."""
        ...


class PhotoProvider(Protocol):
    def project_public(self, *, event_id: int, member_id: int, scope: str) -> dict | None: ...

    def prepare_print_resources(
        self, *, subject: AnswerSubject, selection: PhotoSelection,
    ) -> object:
        """Prepare immutable hash/version resources outside event row locks."""
        ...


class AssetReader(Protocol):
    def authorize_read(
        self, *, actor_id: int | None, asset_id: int, snapshot_id: int | None,
        purpose: ReadPurpose,
    ) -> object: ...


class AgeProvider(Protocol):
    def project(self, *, subject: AnswerSubject, question_id: str) -> dict: ...

    def review_date_locked(
        self, *, subject: AnswerSubject, revision: int, as_of_date: date,
        locks: LockedContext,
    ) -> None: ...
