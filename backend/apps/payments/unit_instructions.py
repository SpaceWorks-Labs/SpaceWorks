"""Per-unit offline payment instructions for the member's own pay view (parity O-B3, H4).

A member who belongs to a unit (district, chapter, branch) pays that unit's treasurer, so the instructions
shown for a charge are the NEAREST ancestor's (the unit's own first), falling back to the space-wide
`MakerspaceBillingSettings.payment_instructions` when no unit on the path has any. The answer names the unit it
came from so the page can say "from the Kochi chapter".

Rules that keep this safe:
* only the charge's OWN member gets it (`viewer.pk == payment.member_id`); pay links, donations and staff views
  never call it with a viewer, so they keep the space-wide text and learn nothing about units;
* only while `membership.units` is on for the charge's space (switch off = the unit data is ignored);
* resolved per page in two queries, never per row;
* a unit with its own instructions replaces the space's UPI QR too (the QR points at the space's VPA, which
  would send a chapter's money to the wrong account) -- the caller hides `upi` when this returns a hit.
"""


def resolve_unit_instructions(rows, viewer):
    """`{payment_id: {"text": str, "unit": {"id","name","code"}}}` for the viewer's own charges that have one."""
    from apps.makerspaces.capability_eligibility import feature_enabled_servable_ids
    from apps.makerspaces.models_member_units import MemberUnit, MembershipUnit

    if viewer is None or not getattr(viewer, "is_authenticated", False):
        return {}
    own = [row for row in rows if row.member_id is not None and row.member_id == viewer.pk]
    if not own:
        return {}
    spaces = set(feature_enabled_servable_ids({row.makerspace_id for row in own}, "membership.units"))
    own = [row for row in own if row.makerspace_id in spaces]
    if not own:
        return {}
    assigned = {(space_id, user_id): unit for space_id, user_id, unit in MembershipUnit.objects.filter(
        makerspace_id__in=spaces, membership__user_id=viewer.pk).values_list(
        "makerspace_id", "membership__user_id", "unit_id")}
    if not assigned:
        return {}
    unit_ids = set(assigned.values())
    units = {unit.pk: unit for unit in MemberUnit.objects.filter(pk__in=unit_ids)}
    candidates = {}
    for space_id in {unit.makerspace_id for unit in units.values()}:
        candidates[space_id] = list(MemberUnit.objects.filter(makerspace_id=space_id).exclude(
            payment_instructions__regex=r"^\s*$").only("id", "name", "code", "path", "payment_instructions"))
    result = {}
    for row in own:
        unit = units.get(assigned.get((row.makerspace_id, viewer.pk)))
        if unit is None:
            continue
        ancestors = [node for node in candidates.get(unit.makerspace_id, ()) if unit.path.startswith(node.path)]
        if not ancestors:
            continue
        nearest = max(ancestors, key=lambda node: len(node.path))
        result[row.pk] = {"text": nearest.payment_instructions,
                          "unit": {"id": nearest.pk, "name": nearest.name, "code": nearest.code}}
    return result
