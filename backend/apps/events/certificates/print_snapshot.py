from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class BadgeSnapshot:
    registration_id: int
    event_id: int
    member_id: int | None
    authorized_fields: tuple[tuple[str, str], ...]
    template_revision: str
    stock: str
    logo_artwork_revision: str | None
    credential_generation: int | None
    credential_render_handle: int | None
    presentation_id: int | None
    presentation_version: int | None
    source_profile_id: int | None
    source_avatar_revision: str | None
    photo_sha256: str | None
    photo_render_handle: int | None
    created_at: datetime
    expires_at: datetime

    @property
    def fields(self):
        return self.authorized_fields
