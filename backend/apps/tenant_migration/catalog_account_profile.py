"""Field snapshot for the account-level profile models and the 0.12.0 field additions that had no snapshot entry.

The four account profile models belong to the person, not to a space (see
`data_export/classification_account_profile.py`), so the tenant dump drops them; the snapshot only has to name
their fields so the catalog guard can prove the model universe is fully reviewed.
"""

FIELD_NAMES = {
    "makerspaces.AccountProfile": frozenset((
        "avatar_key bio created_at domains education github_contributions github_synced_at github_username "
        "headline id institution interests is_visible languages links merged_from_legacy open_notice_pending "
        "public_consented_at public_reconfirm_pending public_visible show_about show_achievements show_activity_graph show_bookings "
        "show_certifications show_education show_events show_experience show_interests show_links show_loans "
        "show_machine_activity show_projects show_skills show_spaces show_speaking show_status skills status "
        "status_note updated_at user").split()),
    "makerspaces.AccountProject": frozenset((
        "created_at description id image_key links position profile public_visible source_submission_id "
        "subtitle tags title updated_at").split()),
    "makerspaces.AccountTimelineEntry": frozenset(
        "description end id kind location order organization profile start title".split()),
    "makerspaces.ProfileAchievement": frozenset(
        "achieved_on created_at description id issuer order profile title url".split()),
}
EXTRA_FIELDS = {
    "card_designs.CardDesign": frozenset({"card_role"}),
    "events.EventCrewMember": frozenset({"kind", "position", "staff_hidden"}),
    "hosting_requests.HostingRequest": frozenset({"requested_kind"}),
    "makerspaces.MembershipInviteLink": frozenset({"unit"}),
}
