"""Release-2 lane L8 (#120, #163B): literal export classification of the key and RLS state.

None of these rows travels: key jobs and search-key salts are rebuilt on a target (its own
keys, its own index), a retired browser key belongs to the source's public site, and a
fixed analytics role is a database login of this deployment only.
"""

OMITTED_MODELS = {
    "encryption.KeyRotationJob": "Deployment-local key job progress; a target runs its own rotations.",
    "encryption.MakerspaceSearchKey": "Deployment-local search-key salt; a target re-indexes under its own key.",
    "encryption.RetiredPublishableKey": "A source browser key kept for its grace window; never valid on a target.",
    "tenant_rls.FixedRoleScope": "A database login of this deployment pinned to one space (L25); never portable.",
}
