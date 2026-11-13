"""Parity O-B2: the "ask for changes" bookkeeping on a join request and the per-plan join-form toggles.

`changes_note` is staff-authored text sent to the applicant (not a credential, not a reference);
`changes_requested_at` and `changes_rounds` are workflow bookkeeping. The plan toggles are closed enums.
The applicant's phone / state / photo reference live inside the already-encrypted `application_answers`
snapshot, so no new personal-data column exists.
"""

EXTRA_FIELDS = {
    "makerspaces.MembershipRequest": "changes_note changes_requested_at changes_rounds",
    "makerspaces.MembershipPlan": "join_photo join_phone join_state",
}


def extend(fields):
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
