"""Deployment ownership of programme coordination omitted from portable exports."""
from apps.tenant_migration.catalog_events_programme_references import DEPLOYMENT_OWNERS


def extend_special_tenant_tables(tables, predicate):
    tables.update({label: predicate((path,)) for label, path in DEPLOYMENT_OWNERS.items()})
    tables["events.SubmissionAssetWork"] = predicate((
        "asset__event__makerspace", "participant_asset__event__makerspace",
    ))
    tables["events.BadgePrintResource"] = predicate(("job__event__makerspace",))
