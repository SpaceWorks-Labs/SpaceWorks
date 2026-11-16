# Decisions, with the reason for each

This is the record of every decision that shapes the SpaceWorks product, its design and how it is built,
**together with the reason**, so the reason is not lost when people move on.

- **D-nnn** is the number of the decision in the maintainers' decision ledger. Numbers are kept so the two can be
  cross-referenced. A later decision wins over an earlier one; replaced decisions stay listed (see
  [Superseded decisions](#superseded-decisions)) and are never deleted.
- Where no reason was recorded, the entry says **Reason not recorded** instead of guessing.
- Letter suffixes (D-135b, D-197a) split one ledger decision into several topics, or mark an addendum.
- Dates are 2026. Entries are grouped by area, newest first within an area. Session mechanics, personal setup
  and private matters are deliberately not recorded here.
- Written 13 November 2026, covering decisions up to D-384.

## Areas

| Area | Entries | File |
|---|---|---|
| Product and scope | 30 | [decisions/product.md](decisions/product.md) |
| Architecture and data | 19 | [decisions/architecture.md](decisions/architecture.md) |
| Security and authentication | 39 | [decisions/security.md](decisions/security.md) |
| Roles and access | 15 | [decisions/roles.md](decisions/roles.md) |
| Money and payments | 23 | [decisions/money.md](decisions/money.md) |
| Modules and areas | 20 | [decisions/modules.md](decisions/modules.md) |
| Hosting and installer | 23 | [decisions/hosting.md](decisions/hosting.md) |
| Mobile apps and API | 10 | [decisions/mobile-api.md](decisions/mobile-api.md) |
| Analytics and reports | 9 | [decisions/analytics.md](decisions/analytics.md) |
| UX and design | 29 | [decisions/ux-design.md](decisions/ux-design.md) |
| Events and community | 19 | [decisions/events.md](decisions/events.md) |
| Equipment and machines | 25 | [decisions/equipment.md](decisions/equipment.md) |
| Testing and release process | 28 | [decisions/testing-release.md](decisions/testing-release.md) |

Total: 289 entries.

## Superseded decisions

Decisions whose status is not "current", with what replaced them (the full text is in the area file).

| Decision | Title | Status | Area |
|---|---|---|---|
| [D-358](decisions/mobile-api.md) | Mobile auth follow-ups | partly superseded by D-361 | Mobile apps and API |
| [D-337](decisions/architecture.md) | Adapter audit, safety auto-off and shelf-check limits | partly superseded by D-348 | Architecture and data |
| [D-311](decisions/equipment.md) | Machine connectivity area (video, logging, notifications) | partly superseded by D-312 and D-320 | Equipment and machines |
| [D-310](decisions/equipment.md) | Uniform, vendor-neutral adapter API in core | partly superseded by D-312 | Equipment and machines |
| [D-309](decisions/equipment.md) | Machine printing automation scope for 0.12.0 | partly superseded by D-310 | Equipment and machines |
| [D-305](decisions/architecture.md) | AccountProfile implementation and handle claiming | partly superseded by D-308 (every account must have a handle) | Architecture and data |
| [D-302](decisions/product.md) | Member profile: status, achievements, projects | partly superseded by D-303 (default visibility) and D-304 (profile is account-level) | Product and scope |
| [D-300](decisions/product.md) | Landing scroll story, landing switch and installer question | partly superseded by D-316 (dark palette values) | Product and scope |
| [D-275](decisions/ux-design.md) | Public home and space directory | partly superseded by D-316 (dark-theme surfaces) | UX and design |
| [D-273](decisions/ux-design.md) | Settings information architecture | partly superseded by D-316 (dark-theme values) | UX and design |
| [D-260](decisions/money.md) | Payments audit rules | partly superseded by D-268 (the 3-decimal currency deferral) | Money and payments |
| [D-239](decisions/hosting.md) | Hybrid self-hosting: every component is an independent choice | partly superseded by D-348 | Hosting and installer |
| [D-237](decisions/security.md) | Backend image base: Debian trixie | superseded by D-262 | Security and authentication |
| [D-234](decisions/hosting.md) | One deployment mode: self-hosted | partly superseded by D-240 | Hosting and installer |
| [D-233](decisions/hosting.md) | Full cloud hosting scope and providers | partly superseded by D-234 | Hosting and installer |
| [D-231](decisions/security.md) | Fix backend image OS CVEs rather than only document them | partly superseded by D-262 | Security and authentication |
| [D-220](decisions/hosting.md) | Install, designer font and machine follow-ups | partly superseded by D-232 | Hosting and installer |
| [D-219](decisions/product.md) | Release 0.12.0 choices: fonts, due dates, privacy, audit, upgrades | partly superseded by D-225 | Product and scope |
| [D-217](decisions/roles.md) | Per-role access matrix | partly superseded by D-219 | Roles and access |
| [D-215](decisions/architecture.md) | Module interconnection research | partly superseded by D-216 | Architecture and data |
| [D-214](decisions/equipment.md) | Contextual inventory lending | partly superseded by D-216 | Equipment and machines |
| [D-197i](decisions/money.md) | Hackathon money and superadmin control details | partly superseded by D-234 and D-236 (hosting-plan wording) | Money and payments |
| [D-189](decisions/security.md) | Control plane access (server-only default) | partly superseded by D-191 | Security and authentication |
| [D-187](decisions/hosting.md) | Hosting limiter built but off by default | partly superseded by D-234 and D-236 | Hosting and installer |
| [D-185](decisions/hosting.md) | Superadmin hosting controls | partly superseded by D-187, D-195 | Hosting and installer |
| [D-169](decisions/ux-design.md) | README tagline, banner and calendar invites | partly superseded by D-247 (tagline wording) | UX and design |
| [D-142](decisions/equipment.md) | Machine job policy answers | partly superseded by D-174 | Equipment and machines |
| [D-122](decisions/testing-release.md) | Version numbering | partly superseded by D-146 | Testing and release process |
| [D-108](decisions/testing-release.md) | Pull-request CI is checks only | partly superseded by D-238 | Testing and release process |
| [D-106](decisions/testing-release.md) | README banner and screenshots | partly superseded by D-168 | Testing and release process |
| [D-96](decisions/product.md) | Research picks: donations and calendar sync | partly superseded by D-128c | Product and scope |
| [D-66](decisions/security.md) | MFA rollout and reset authority | partly superseded by D-128a | Security and authentication |
| [D-63](decisions/roles.md) | One account per person | partly superseded by D-65 | Roles and access |
| [D-46](decisions/hosting.md) | Hosting requests on a managed platform | partly superseded by D-190 | Hosting and installer |
| [D-16a](decisions/events.md) | Submission files: scanning, previews, storage, retention | partly superseded by D-138 | Events and community |

## How to record a decision

Add every new decision in the same commit as the code that makes it, so the reason is written down while it is fresh.

```
### D-nnn — Short title
- **Area:** one of the areas above
- **Date:** day and month
- **Decision:** one or two plain sentences: what is now true.
- **Why:** the reason. If you do not know it, write "Reason not recorded".
- **Status:** current, or "superseded by D-xxx", or "partly superseded by D-xxx".
- **Implemented in:** repository paths that exist.
```

Rules: always record the reason; never delete or rewrite a decision, change its status and list it above;
explain internal words once; no secrets, emails, personal names or machine paths; keep area files under about
600 lines (start a second file for the area if one grows past that). The `handover/` folder (CONTINUE-HERE and
TODO for the next session) is git-ignored and never holds decisions.
