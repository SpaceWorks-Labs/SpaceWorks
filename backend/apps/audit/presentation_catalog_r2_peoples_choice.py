"""Audit presentation for lane r2-peoples-choice (#181 S3).

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time, so
these entries name the action only. A ballot entry never names the project voted for.
"""

from .presentation_catalog_types import P


ENTRIES = (
    P("event.peoples_choice.updated", "People's choice settings changed"),
    P("event.peoples_choice.ballot_cast", "People's choice vote cast or changed"),
    P("event.peoples_choice.vote_voided", "People's choice vote voided"),
    P("event.peoples_choice.published", "People's choice result published"),
)
