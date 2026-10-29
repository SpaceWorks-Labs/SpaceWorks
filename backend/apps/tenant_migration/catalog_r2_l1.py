"""Release-2 lane L1 (public event surface): tenant-dump field snapshot and authority.

* `EventShortLink` travels with its event, retired rows too, so their codes stay
  reserved on the target. The code is a public identifier; `unique_values_r2_l1`
  preserves it and refuses a collision with `short_code_conflict` (a silent remap would
  break printed links; the operator regenerates on the target if it ever fires).
* `EventShortLinkVisitDay` is an aggregate count with no person in it.
* `EventEmbedPolicy` is inert configuration: it only narrows who may frame the space's
  cards, and nothing frames them until `events.embed` is on in the target.
* `Event.join_url_encrypted` is deployment-key ciphertext the target cannot read: it is
  cleared and re-entered there, like every encrypted integration credential.
"""

FIELD_NAMES = {
    "events.EventShortLink": frozenset(
        "id event makerspace code created_by created_at retired_at retired_by".split()),
    "events.EventShortLinkVisitDay": frozenset("id event makerspace day count".split()),
    "events.EventEmbedPolicy": frozenset(
        "id makerspace enabled allowed_origins updated_by updated_at".split()),
}
EXTRA_FIELDS = {
    "events.Event": frozenset({"listing", "page_state", "delivery_mode", "join_url_encrypted"}),
    "events.EventSeries": frozenset({"listing"}),
    "makerspaces.Makerspace": frozenset({"public_closed_notice", "public_reopens_on"}),
}


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    return (
        *same("events.Event", "listing page_state", disposition.PRESERVE,
              "Who can find the event and whether its page is up are tenant publication controls."),
        *same("events.EventSeries", "listing", disposition.PRESERVE,
              "The series default for who can find new occurrences is tenant publication content."),
        *same("events.Event", "join_url_encrypted", disposition.RESET,
              "Deployment-key ciphertext of the meeting link; cleared and re-entered on the target."),
        *same("events.EventEmbedPolicy", "enabled allowed_origins", disposition.PRESERVE,
              "An embed allow-list only narrows framing and is inert until events.embed is on."),
        *same("makerspaces.Makerspace", "public_closed_notice public_reopens_on", disposition.PRESERVE,
              "The closed-for-now banner is public page text; no lifecycle state."),
    )
