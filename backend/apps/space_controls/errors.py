"""Typed refusals for paused and read-only spaces.

Both subclass the source gate's ``SourceMigrationGateClosed`` on purpose: every boundary
that already handles a frozen tenant (the HTTP gate renders 423, fan-out sweeps skip and
count, staff writers map it to ``tenant_gated``) handles a paused or read-only space the
same way, so no caller needs a second code path.
"""

from rest_framework import status
from rest_framework.exceptions import APIException

from apps.tenant_migration.gate_errors import SourceMigrationGateClosed


class SpaceSuspended(SourceMigrationGateClosed):
    code = "space_suspended"

    def __init__(self):
        super().__init__("This space is paused by the platform operator.")


class SpaceReadOnly(SourceMigrationGateClosed):
    code = "space_read_only"

    def __init__(self):
        super().__init__(
            "This space is read-only: you can view and export, but nothing new can be created.",
        )


class SpaceControlConflict(APIException):
    """A typed 409 ``{"detail", "code"}`` for a control that does not apply now."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, code, detail):
        super().__init__({"detail": detail, "code": code}, code=code)
        self.detail = {"detail": detail, "code": code}
