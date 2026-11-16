"""The `account.converted` audit row the unification migration writes per staff account.

Kept outside `migrations/` so the audit drift guards see its literal action and metadata
(the same historical-model writer the fixed-roles migration uses; no live event).
"""

from apps.makerspaces.migration_support.fixed_roles_audit import record


def record_conversion(space_id, user_id, *, holds, roles_kept, models, alias):
    return record(space_id, "account.converted", "accounts.user", user_id, models=models, alias=alias,
                  meta={"decision": "converted", "holds": list(holds), "roles_kept": list(roles_kept)})
