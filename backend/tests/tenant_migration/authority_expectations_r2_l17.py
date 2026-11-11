"""Literal section 3a dispositions for lane L17's settings-authority rows (local only)."""

from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D


def _fields(label, names, dispositions):
    return [((label, name), (dispositions,)) for name in names.split()]


L17_EXPECTED = dict([
    *_fields("makerspaces.ModuleSettingsGrant", "module granted_at revoked_at", D.PRESERVE),
    *_fields("makerspaces.ModuleSettingLock", "setting_key note created_at released_at", D.PRESERVE),
])
