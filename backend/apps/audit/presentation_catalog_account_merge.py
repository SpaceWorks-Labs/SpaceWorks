"""Audit presentation for interactive account merges (decision #65; lane U-C).

Never a code, an identifier or an address: only the proof method, the source account id
(a shell after the merge), counts per disposition and the role slugs gained.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("account.merge_started", "Account link started", ("method",)),
    P("account.merge_proof_failed", "Account link proof rejected", ("method", "attempts")),
    P("account.merge_cancelled", "Account link cancelled", ("method",)),
    P("account.merged", "Accounts linked into one",
      ("proof_method", "source_id", "record_id", "counts", "roles_gained", "grace_opened")),
)
