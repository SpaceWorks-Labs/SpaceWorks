"""Object-reference rules for release 2 L3 (ID cards): every card object is PRIVATE.

Design artwork and programme/event card photos are canonical bytes of exported rows.
Temporary job results (`CardJob.result_key`) and the deployment font cache
(`CardFont.font_key`) are not archive content: their rows are omitted and their field
names are not object-key names, so neither travels.
"""


def field_object_rules(FieldObjectRule, BucketRule, ReferencePolicy):
    return (
        FieldObjectRule("card_designs.CardDesignAsset", "object_key", BucketRule.PRIVATE),
        FieldObjectRule("id_programmes.IdProgrammeCard", "photo_object_key", BucketRule.PRIVATE),
        FieldObjectRule("events.EventIdCard", "photo_object_key", BucketRule.PRIVATE),
    )
