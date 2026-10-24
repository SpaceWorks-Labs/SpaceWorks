"""Portable private bytes of stage-form uploads and finance attachments.

Only rows whose accepted bytes exist (``ready``/``attached``) contribute to a tenant
migration's object closure. Purge and retention deletion stay with the packages' own
FK-free cleanup locators, so the purge closure is unchanged.
"""

PORTABLE_ASSET_STATES = ("ready", "attached")


def collect_portable_keys(makerspace, add):
    from apps.events.staged_forms.upload_models import StageFormAsset
    from apps.payments.event_payouts.attachment_models import FinanceAttachment
    for rows in (StageFormAsset.objects.filter(event__makerspace=makerspace),
                 FinanceAttachment.objects.filter(makerspace=makerspace)):
        for key in rows.filter(state__in=PORTABLE_ASSET_STATES).values_list("object_key", flat=True).iterator(chunk_size=500):
            add(key)
