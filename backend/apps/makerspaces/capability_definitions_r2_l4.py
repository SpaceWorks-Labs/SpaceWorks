"""Release-2 lane L4: the membership lifecycle (#69, #71, #95, #97, #128 C-13).

Every switch sits under `membership`, is off by default, and keeps its data when turned
off (#95, #128 C-8). What always runs regardless of these switches, because it is the
record itself rather than a feature: the gapless member number is assigned at
activation, each term freezes what it was sold for, and term standing changes are
written to the append-only term history.

* `membership.plan_rules` -- financial-year, fixed-end and lifetime plans, a separate
  renewal price, per-plan joining fee / rejoin rule / payment timing / join mode / form,
  and the late-renewal rule. Off: plan writes refuse these fields; plans that already
  use them keep their stored rules so no member's term changes underneath them.
* `membership.public_plans` -- plan cards and per-plan pages on the public site, and the
  applicant choosing a plan when they ask to join.
* `membership.renewal_desk` -- the renewal worklist, manual bulk reminders (one per
  member per day) and extending a membership by hand with a reason.
* `membership.import` -- CSV/Excel member import into pending, invited memberships.
* `membership.admission_tools` -- multi-use invite links and bulk approve/reject.
* `membership.member_numbers` -- show member numbers and set their printed pattern.
* `membership.records` -- state code, GSTIN and staff notes on the member record.
* `membership.titles` -- display-only member titles (never permissions).
* `membership.consent` -- the consent ledger members can withdraw from.
* `membership.erasure` -- a member asks one space to anonymise their membership data.
* `membership.history` -- the membership history timeline in words.
* `membership.register_tools` -- standing filters and the member-register CSV export.
* `membership.insights` -- renewal, collection, bridge and funnel reports.
* `membership.monthly_summary` -- the monthly staff summary email (opt-out per person).
"""


def definitions(feature):
    def member(key, label, description, **extra):
        return feature(f"membership.{key}", "membership", label, description, **extra)

    return (
        member("plan_rules", "Plan types and rules",
               "Financial-year, fixed-end and lifetime plans; renewal prices; per-plan fees, rejoin "
               "rules, payment timing, join mode and application form; late-renewal rule."),
        member("public_plans", "Public plan pages",
               "Plan cards and per-plan pages on the public site; applicants choose a plan when joining."),
        member("renewal_desk", "Renewal desk",
               "Renewal worklist, manual bulk reminders and extending a membership with a reason."),
        member("import", "Member import",
               "Import members from CSV or Excel as pending memberships with emailed invitations."),
        member("admission_tools", "Invite links and bulk decisions",
               "Multi-use invite links with limits and expiry; bulk approve or reject join requests."),
        member("member_numbers", "Member numbers",
               "Show each member's fixed number and choose how it is printed."),
        member("records", "Member record fields",
               "State code, GSTIN and staff-only notes on each member record."),
        member("titles", "Member titles",
               "Display-only titles such as Treasurer; they grant no permissions."),
        member("consent", "Consent ledger",
               "Record what members agreed to, at which notice version, and let them withdraw."),
        member("erasure", "Erasure requests",
               "Members ask this space to anonymise their membership data; staff approve or reject."),
        member("history", "Membership history",
               "A timeline in words of each membership's terms, renewals and changes."),
        member("register_tools", "Register filters and export",
               "Filter the register by standing and export it as CSV.", requires_modules=("reports",)),
        member("insights", "Membership insights",
               "Renewal, collection, bridge, breakdown, expiry and funnel reports.",
               requires_modules=("reports",)),
        member("monthly_summary", "Monthly staff summary",
               "A monthly membership summary email to staff, each of whom can opt out.",
               requires_modules=("reports",)),
    )
