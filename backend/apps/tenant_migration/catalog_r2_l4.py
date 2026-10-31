"""Release-2 lane L4 (membership lifecycle) Lane D field snapshot.

`FIELD_NAMES` adds whole entries for new models; `EXTRA_FIELDS` appends new fields
to existing models. Imported by `tenant_dump_field_snapshot`. The member number is
unique per space only, so a dump into a new space keeps it as it is. The invite link
model is deployment-local and never in a dump (a bearer credential).
"""

from apps.data_export.classification_r2_l4 import EXPORTED_FIELDS, FIELD_ADDITIONS

FIELD_NAMES = {label: frozenset(names.split()) for label, names in EXPORTED_FIELDS.items()}
# Projected (travelling) models; the invite link is listed for the field snapshot only
# and is dropped through `data_export` OMITTED_MODELS.
PROJECTED_LABELS = frozenset(FIELD_NAMES)
FIELD_NAMES["makerspaces.MembershipInviteLink"] = frozenset(
    "id makerspace code_digest label plan max_uses uses expires_at revoked_at created_by created_at".split())

EXTRA_FIELDS = dict(FIELD_ADDITIONS)
