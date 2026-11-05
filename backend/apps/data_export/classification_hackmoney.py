"""Hack-money lane (#180, #181): export classification for the payments-side additions.

Exported with the space: the per-space event money settings (prize tax rate/threshold switch and
the accepted payee templates) and a sponsorship charge's event and prize-pool earmark. The prize
shares, claims and outcomes are events programme rows (`tenant_migration/catalog_hackmoney`); a
claim's payee details and PAN are always-encrypted scoped PII and travel only as their envelopes.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "payments.EventMoneySettings": "id makerspace prize_tds_enabled prize_tds_rate prize_tds_threshold "
                                   "payee_templates version updated_by updated_at",
}
#: New columns on an existing exported model.
EXTRA_FIELDS = {"payments.SponsorshipCharge": "event earmark"}
DATASET_SPECS = {
    "payments.EventMoneySettings": ("finance/event_money_settings.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({("payments.EventMoneySettings", "updated_by")})
# The accepted payee templates are [country, method] pairs: no ids.
JSON_FIELDS = frozenset({("payments.EventMoneySettings", "payee_templates")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, names in EXTRA_FIELDS.items():
        current = fields[label]
        fields[label] = (current + " " + names) if isinstance(current, str) else frozenset(current) | set(names.split())
    return fields
