"""Parity O-B2: the join funnel and the member register.

* `membership.ask_changes` -- staff can send a join request back for changes; the applicant edits and resubmits
  once. OFF by default; a request already waiting for changes keeps working when it is switched off (the
  applicant can still resubmit or cancel, staff can still decline).
* `membership.join_photo` -- a plan may ask for a member-card photo on the join form (off / optional /
  required). The photo never replaces one the member's card already has. OFF by default.
* `membership.join_contact_fields` -- a plan may show a phone number and a state on the join form (hidden /
  optional / required). The state feeds the GST place of supply. OFF by default.
* `membership.register_bulk` -- bulk title, unit, reminder and card actions from the member register
  (at most 200 rows per call, a result for every row). OFF by default.
"""


def definitions(feature):
    return (
        feature("membership.ask_changes", "membership", "Ask applicants for changes",
                "Send a join request back with a note; the applicant edits their answers and resubmits once."),
        feature("membership.join_photo", "membership", "Photo on the join form",
                "Plans can ask applicants for a member-card photo (off, optional or required)."),
        feature("membership.join_contact_fields", "membership", "Phone and state on the join form",
                "Plans can show a phone number and a state (used for GST place of supply) on the join form."),
        feature("membership.register_bulk", "membership", "Bulk actions on the member register",
                "Assign a title, move to a unit, send a renewal reminder or issue and email cards for up to 200 "
                "members at once."),
    )
