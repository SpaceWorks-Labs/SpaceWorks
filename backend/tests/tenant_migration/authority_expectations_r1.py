"""Literal section 3a dispositions for the programmes merged into release 1.

Account lifecycle (deletion/restore), native device grants, composed public pages and
event session identities, addressed messaging, and per-makerspace mail providers each
added authority overrides; these are the reviewed literals, not derived from code.
"""

from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D


def _fields(label, names, dispositions):
    if not isinstance(dispositions, tuple):
        dispositions = (dispositions,)
    return [((label, name), dispositions) for name in names.split()]


R1_EXPECTED = dict([
    # Device grants are deployment-local credentials; the device re-enrolls on the target.
    *_fields("accounts.DeviceGrant", "credential_generation login_method staff_makerspace_id", D.DROP),
    # Account deletion keeps its timeline; target-owned erasure material never travels.
    *_fields("accounts.User", "account_purged_at deletion_purge_after deletion_requested_at purge_started_at",
             (D.PRESERVE, D.RESET)),
    *_fields("accounts.User", "account_restored_at deletion_email_ciphertext deletion_username", D.RESET),
    # Composed pages: drafts, revisions and session identities travel; publication does not.
    *_fields("events.EventPage", "draft_revision editorial_document", D.PRESERVE),
    *_fields("events.EventPage", "published_revision", D.RESET),
    *_fields("events.EventPageRevision",
             "id page document schema_version source_anchor_start created_at created_by", D.PRESERVE),
    *_fields("events.EventPageRevisionAsset", "id revision asset slot", D.PRESERVE),
    *_fields("events.EventPageRevisionMember", "id revision profile slot", D.PRESERVE),
    *_fields("events.EventSession", "identity", D.PRESERVE),
    *_fields("events.EventSessionAlias", "id identity page slug", D.PRESERVE),
    *_fields("events.EventSessionIdentity", "id page", D.PRESERVE),
    *_fields("makerspaces.MakerspacePublicPage", "id makerspace draft_revision version", D.PRESERVE),
    *_fields("makerspaces.MakerspacePublicPage", "published_revision", D.RESET),
    *_fields("makerspaces.MakerspacePublicPageAsset",
             "id page object_key alt_text size_bytes created_at", D.PRESERVE),
    *_fields("makerspaces.MakerspacePublicPageRevision",
             "id page document schema_version created_at created_by", D.PRESERVE),
    *_fields("makerspaces.MakerspacePublicPageRevisionAsset", "id revision asset slot", D.PRESERVE),
    *_fields("makerspaces.MakerspacePublicPageRevisionMember", "id revision profile slot", D.PRESERVE),
    *_fields("makerspaces.PublicHandle", "makerspace organization", (D.PRESERVE, D.DROP)),
    # Imported communication history never authorizes target sending.
    *_fields("integrations.MessagingConsent",
             "action configuration_generation endpoint lifted_suppression_id sender_key", D.RESET),
    *_fields("integrations.WhatsAppTemplateBinding", "is_active needs_review", D.RESET),
    # The target operator configures mail transport; source secrets never travel.
    *_fields("makerspaces.Makerspace", "email_provider email_provider_config", D.RESET),
])
