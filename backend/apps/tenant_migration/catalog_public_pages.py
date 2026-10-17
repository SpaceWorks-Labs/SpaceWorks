"""Reviewed v1 page fields. Global organization content never travels with a tenant."""

EXPORTED_FIELDS = {
    "makerspaces.MakerspacePublicPage": "id makerspace version draft_revision published_revision",
    "makerspaces.MakerspacePublicPageRevision": "id page schema_version created_by created_at document",
    "makerspaces.MakerspacePublicPageAsset": "id page object_key size_bytes alt_text created_at",
    "makerspaces.MakerspacePublicPageRevisionAsset": "id revision asset slot",
    "makerspaces.MakerspacePublicPageRevisionMember": "id revision profile slot",
    "events.EventPageRevision": "id page schema_version source_anchor_start document created_by created_at",
    "events.EventPageRevisionAsset": "id revision asset slot",
    "events.EventPageRevisionMember": "id revision profile slot",
    "events.EventSessionIdentity": "id page",
    "events.EventSessionAlias": "id page identity slug",
}
GLOBAL_FIELDS = {
    "organizations.OrganizationPublicPage": "id organization version draft_revision published_revision",
    "organizations.OrganizationPublicPageRevision": "id page schema_version created_by created_at document",
    "organizations.OrganizationPublicPageAsset": "id page object_key size_bytes alt_text created_at",
    "organizations.OrganizationPublicPageRevisionAsset": "id revision asset slot",
    "organizations.OrganizationPublicPageRevisionMember": "id revision profile slot",
    "organizations.OrganizationPublicPageStorage": "id organization used_bytes",
}
FIELD_NAMES = {label: frozenset(fields.split()) for label, fields in {**EXPORTED_FIELDS, **GLOBAL_FIELDS}.items()}
FIELD_NAMES["makerspaces.PublicPageObjectCleanup"] = frozenset(
    "id owner_kind owner_id page_id object_key size_bytes due_at attempts completed_at created_at".split())
OMITTED_MODELS = {label: "Organization-owned global editorial content; deployment backup only."
                  for label in GLOBAL_FIELDS}
OMITTED_MODELS["makerspaces.PublicPageObjectCleanup"] = "Deployment-local retryable byte-cleanup journal; never target authority."
USER_FIELDS = frozenset({("makerspaces.MakerspacePublicPageRevision", "created_by"),
                         ("events.EventPageRevision", "created_by")})
EXCLUDED_USER_EDGES = {("organizations.OrganizationPublicPageRevision", "created_by"):
                       "Global organization editorial attribution never contributes to tenant closure."}
DATASETS = {
    "makerspaces.MakerspacePublicPage": ("pages/makerspace_pages.csv", "makerspace"),
    "makerspaces.MakerspacePublicPageRevision": ("pages/makerspace_revisions.csv", "page__makerspace"),
    "makerspaces.MakerspacePublicPageAsset": ("pages/makerspace_assets.csv", "page__makerspace"),
    "makerspaces.MakerspacePublicPageRevisionAsset": ("pages/makerspace_revision_assets.csv", "revision__page__makerspace"),
    "makerspaces.MakerspacePublicPageRevisionMember": ("pages/makerspace_revision_members.csv", "revision__page__makerspace"),
    "events.EventPageRevision": ("events/page_revisions.csv", "page__makerspace"),
    "events.EventPageRevisionAsset": ("events/page_revision_assets.csv", "revision__page__makerspace"),
    "events.EventPageRevisionMember": ("events/page_revision_members.csv", "revision__page__makerspace"),
    "events.EventSessionIdentity": ("events/session_identities.csv", "page__makerspace"),
    "events.EventSessionAlias": ("events/session_aliases.csv", "page__makerspace"),
}


def authority_entries(authority, D):
    return [((label, field), authority(D.RESET if field == "published_revision" else D.PRESERVE,
             "Authored history is retained; target publication and disclosures require fresh consent."))
            for label, fields in EXPORTED_FIELDS.items() for field in fields.split()]
