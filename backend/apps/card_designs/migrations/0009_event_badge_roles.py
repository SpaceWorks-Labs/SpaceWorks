"""E-B1: `CardDesign.card_role`, a per-role variant of an event card design.

The four "one design per target" uniqueness constraints now only bind the base design (no role); a role
variant is unique per (target, role). Existing rows keep `card_role = NULL`, so nothing changes for them.
"""
from django.db import migrations, models
from django.db.models import Q

BASE, ROLE = Q(card_role__isnull=True), Q(card_role__isnull=False)
UNTARGETED = Q(plan__isnull=True, title__isnull=True, programme__isnull=True, organization__isnull=True,
               event__isnull=True, ticket_type__isnull=True)
ORG = Q(organization__isnull=False, event__isnull=True)
EVENT = Q(event__isnull=False, ticket_type__isnull=True)
TICKET = Q(ticket_type__isnull=False)

# name -> (fields, base condition, role condition, role constraint name)
CHANGED = (
    ("uniq_card_design_space_default", ["makerspace", "domain"], UNTARGETED, "uniq_card_design_space_role"),
    ("uniq_card_design_org_default", ["organization", "domain"], ORG, "uniq_card_design_org_role"),
    ("uniq_card_design_event", ["event", "domain"], EVENT, "uniq_card_design_event_role"),
    ("uniq_card_design_ticket_type", ["ticket_type", "domain"], TICKET, "uniq_card_design_ticket_type_role"),
)


def _operations():
    ops = [migrations.AddField("carddesign", "card_role", models.CharField(
        blank=True, null=True, max_length=12,
        choices=[("crew", "Crew"), ("volunteer", "Volunteer"), ("speaker", "Speaker"), ("mentor", "Mentor"),
                 ("judge", "Judge"), ("organiser", "Organiser")]))]
    ops += [migrations.RemoveConstraint("carddesign", name) for name, *_ in CHANGED]
    for name, fields, condition, role_name in CHANGED:
        ops.append(migrations.AddConstraint("carddesign", models.UniqueConstraint(
            fields=fields, condition=condition & BASE, name=name)))
        ops.append(migrations.AddConstraint("carddesign", models.UniqueConstraint(
            fields=[*fields, "card_role"], condition=condition & ROLE, name=role_name)))
    ops.append(migrations.AddConstraint("carddesign", models.CheckConstraint(
        name="card_design_role_event_card_only", condition=Q(card_role__isnull=True) | Q(domain="event_card"))))
    return ops


class Migration(migrations.Migration):
    dependencies = [("card_designs", "0008_numbering_org_default")]
    operations = _operations()
