"""Release-2 lane L1 (public event surface): literal export classification.

* `EventShortLink` -- tenant configuration exported with its event: the code (a public
  identifier, never a secret), timestamps, and `created_by`/`retired_by` as actor references.
* `EventShortLinkVisitDay` -- an aggregate daily count; no IP, agent, referrer or person.
* `EventEmbedPolicy` -- the space's framing allow-list (partner origins, no PII).
* New `Event` columns: `listing`, `page_state`, `delivery_mode` are plain settings;
  `join_url_encrypted` is deployment-key ciphertext and is always omitted (the join link
  is re-entered on the target, like every encrypted integration credential).
* `EventSeries.listing` and the Makerspace closed-for-now banner are plain settings.
"""

from .types import TenantPredicate

EXPORTED_FIELDS = {
    "events.EventShortLink": "id event makerspace code created_by created_at retired_at retired_by",
    "events.EventShortLinkVisitDay": "id event makerspace day count",
    "events.EventEmbedPolicy": "id makerspace enabled allowed_origins updated_by updated_at",
}
EXTRA_FIELDS = {
    "events.Event": "listing page_state delivery_mode join_url_encrypted",
    "events.EventSeries": "listing",
    "makerspaces.Makerspace": "public_closed_notice public_reopens_on",
}
DATASET_SPECS = {
    "events.EventShortLink": ("events/short_links.csv", TenantPredicate(("makerspace",))),
    "events.EventShortLinkVisitDay": ("events/short_link_visits.csv", TenantPredicate(("makerspace",))),
    "events.EventEmbedPolicy": ("events/embed_policy.csv", TenantPredicate(("makerspace",))),
}
ALWAYS_OMITTED = {
    ("events.Event", "join_url_encrypted"): "Encrypted meeting join link; re-enter it on the target.",
}
RELATIONAL_USER_FIELDS = frozenset({
    ("events.EventShortLink", "created_by"),
    ("events.EventShortLink", "retired_by"),
    ("events.EventEmbedPolicy", "updated_by"),
})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
