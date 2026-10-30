"""Release-2 lane L4 (membership lifecycle) export classification.

Imported by the `classification` barrel. `EXPORTED_FIELDS` adds new models,
`FIELD_ADDITIONS` appends new fields to existing models, `OMITTED_MODELS` names
deployment-local rows that never travel.
"""

EXPORTED_FIELDS = {}

FIELD_ADDITIONS = {
    "makerspaces.Makerspace": "financial_year_start_month",
}

OMITTED_MODELS = {}
