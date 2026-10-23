"""Release-2 lane L4 (membership lifecycle) Lane D field snapshot.

`FIELD_NAMES` adds whole entries for new models; `EXTRA_FIELDS` appends new fields
to existing models. Imported by `tenant_dump_field_snapshot`.
"""

FIELD_NAMES = {}

EXTRA_FIELDS = {
    "makerspaces.Makerspace": "financial_year_start_month",
}
