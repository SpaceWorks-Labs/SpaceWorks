"""The shape of one curated analytics view, and how it is rendered for each audience.

A view is declared as data: its columns (each with a description, so the documentation and
the guard tests read the same source), a FROM clause naming tables as ``{app.Model}``
placeholders, and the expression that yields the owning makerspace. Rendering wraps it per
audience:

* ``space`` (``spaceworks_analytics``): rows of the login's own space only. The explicit
  ``spaceworks_rls_fixed_scope(current_user)`` filter, the analytics switch and the
  servability of the space are checked in the view, and L8's RESTRICTIVE fixed-role policy
  applies to every table it reads (the view owner is in ``spaceworks_rls_fixed``). PII
  columns are NULL unless the space turned ``show_member_details`` on.
* ``platform`` (``spaceworks_analytics_platform``): every space, PII always NULL.

A ``lookup`` view also lists platform-wide rows (built-in machine types; people who belong
to the space) that the fixed-role policy hides. It is owned by the platform view owner, so
the explicit filter above is its scoping, and it never exposes more than the owning space
may see.
"""

import re
from dataclasses import dataclass, field

from django.apps import apps

_TABLE = re.compile(r"\{([a-z_]+\.[A-Za-z]+)\}")


@dataclass(frozen=True)
class Col:
    name: str
    expr: str
    description: str
    # Personal data: NULL unless the space allows member details (never on the platform).
    pii: bool = False
    pii_type: str = "text"


@dataclass(frozen=True)
class View:
    name: str
    domain: str
    description: str
    source: str
    makerspace: str
    columns: tuple[Col, ...]
    lookup: bool = False
    # Rows owned by no space (e.g. built-in machine types) are listed in a lookup view.
    include_unowned: bool = False
    since: int = 1
    extra: dict = field(default_factory=dict)
    # Module or capability keys that must be on for the space (decision 218: off removes it
    # everywhere). None means the domain's own switch (`render.DOMAIN_SWITCHES`); () means none.
    requires: tuple[str, ...] | None = None

    def models(self):
        return tuple(dict.fromkeys(_TABLE.findall(self.source)))

    def installed(self):
        for label in self.models():
            try:
                apps.get_model(label)
            except LookupError:
                return False
        return True

    def resolved_source(self):
        def table(match):
            return 'public."' + apps.get_model(match.group(1))._meta.db_table + '"'
        return _TABLE.sub(table, self.source)


def q(name):
    return '"' + name.replace('"', '""') + '"'
