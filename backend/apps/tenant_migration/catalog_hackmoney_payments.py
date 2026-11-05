"""Hack-money lane (#180 G8/G13, #181 G7): tenant-dump catalogue for the payments-side additions.

The per-space event money settings travel with the space (data_export `classification_hackmoney`);
a sponsorship charge keeps the event and prize-pool earmark it was agreed for.
"""

FIELD_NAMES = {
    "payments.EventMoneySettings": frozenset("id makerspace prize_tds_enabled prize_tds_rate prize_tds_threshold "
                                             "payee_templates version updated_by updated_at".split()),
}
EXTRA_FIELDS = {"payments.SponsorshipCharge": frozenset({"event", "earmark"})}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("payments.EventMoneySettings", "prize_tds_enabled prize_tds_rate prize_tds_threshold payee_templates",
              keep, "The space's own prize-tax proposal and payee choices; the deployment ceiling still applies."),
        *same("payments.SponsorshipCharge", "earmark", keep, "What the sponsor's money was agreed for."),
    )
