"""Names of the analytics schemas and database roles.

Roles are cluster-wide in PostgreSQL while views and grants live in one database, so every
role this app makes carries a short tag derived from the database name: two SpaceWorks
databases on one cluster (or a test database next to the dev one) never share a reader or
an owner, and a login made for one database holds no grant in another. The one shared
name is L8's NOLOGIN group ``spaceworks_rls_fixed``, which grants nothing by itself.

* ``owner``  -- NOLOGIN, member of ``spaceworks_rls_fixed``: owns the space views, so L8's
  RESTRICTIVE fixed-role policy applies to every table a space view reads.
* ``powner`` -- NOLOGIN: owns the platform views and the space lookup views.
* ``reader`` / ``preader`` -- NOLOGIN: hold USAGE and SELECT on one schema's views.
  A login is a member of exactly one of them and owns nothing.
"""

import hashlib
import re

SPACE_SCHEMA = "spaceworks_analytics"
PLATFORM_SCHEMA = "spaceworks_analytics_platform"
ADMIN_SCHEMA = "spaceworks_analytics_admin"
FIXED_GROUP = "spaceworks_rls_fixed"
LOGIN_PREFIX = "sw_an_"


def tag(database_name):
    return hashlib.sha256(database_name.encode("utf-8")).hexdigest()[:8]


def roles(database_name):
    t = tag(database_name)
    return {
        "owner": f"sw_analytics_owner_{t}",
        "powner": f"sw_analytics_powner_{t}",
        "reader": f"sw_analytics_reader_{t}",
        "preader": f"sw_analytics_preader_{t}",
    }


def login_name(database_name, makerspace_id, suffix):
    """``sw_an_<tag>_s<space>_<6 hex>`` for a space, ``sw_an_<tag>_p_<6 hex>`` for the platform."""
    scope = "p" if makerspace_id is None else f"s{int(makerspace_id)}"
    if not re.fullmatch(r"[0-9a-f]{6}", suffix):
        raise ValueError("A login suffix is six lowercase hex digits.")
    return f"{LOGIN_PREFIX}{tag(database_name)}_{scope}_{suffix}"
