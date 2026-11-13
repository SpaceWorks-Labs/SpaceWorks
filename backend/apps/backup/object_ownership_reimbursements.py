"""Object-reference rules for stage-form files and core finance attachments.

Canonical bytes are retention-aware (projection: object_reference_retention.
private_upload_projection). Staging keys and the permanent FK-free cleanup locators are
coordination, never archive content.
"""


def field_object_rules(FieldObjectRule, BucketRule, ReferencePolicy):
    coordination = ReferencePolicy.COORDINATION_ONLY
    return (
        FieldObjectRule("events.StageFormAsset", "object_key", BucketRule.PRIVATE, retention_aware=True),
        FieldObjectRule("events.StageFormAsset", "staging_key", BucketRule.PRIVATE, coordination,
                        coordination_path="event__makerspace_id", coordination_reason="stage_upload_staging"),
        FieldObjectRule("events.StageFileCleanup", "object_key", BucketRule.PRIVATE, coordination,
                        coordination_path="tenant_id", coordination_reason="permanent_stage_file_cleanup"),
        FieldObjectRule("events.StageFileCleanup", "staging_key", BucketRule.PRIVATE, coordination,
                        coordination_path="tenant_id", coordination_reason="permanent_stage_file_cleanup"),
        FieldObjectRule("payments.FinanceAttachment", "object_key", BucketRule.PRIVATE, retention_aware=True),
        FieldObjectRule("payments.FinanceAttachment", "staging_key", BucketRule.PRIVATE, coordination,
                        coordination_path="makerspace_id", coordination_reason="finance_upload_staging"),
        FieldObjectRule("payments.FinanceObjectCleanup", "object_key", BucketRule.PRIVATE, coordination,
                        coordination_path="source_makerspace_id", coordination_reason="permanent_finance_cleanup"),
        FieldObjectRule("payments.FinanceObjectCleanup", "staging_key", BucketRule.PRIVATE, coordination,
                        coordination_path="source_makerspace_id", coordination_reason="permanent_finance_cleanup"),
    )
