---
title: Roadmap
group: Project
order: 60
summary: What is being worked on next, stated only where it is factual and without dates.
---

# Roadmap

Space Works does not publish dated promises. This page lists only work that is actually underway or openly
acknowledged as further work, with no delivery dates.

## In development

- **Native Android and iOS apps.** A Kotlin Android app and a Swift iOS app are in development, built against
  the public API contract and the brand design system. The server side already supports them: signed device
  identity, native device grants, app registrations and association files, and a deployment-owned app name.
  See [Connect a branded native app](../mobile-integration.md).
## Ongoing focus

- Reliable self-hosting: backup-first updates from published releases, restore drills and clearer recovery
  steps.
- Complete makerspace operations across the full set of modules for the public, members, staff and
  superadmins.
- Continued accessibility, mobile, reporting and operational resilience work.

## Further work that is acknowledged

- **Hardware integration.** Connected devices already provide signed device identity, printer reports and
  label commands. Broader CNC and controller integration and door or access-control integration remain future
  work.
- **Cloud recipes on real accounts.** The cloud and free-profile recipes have been checked against
  configuration but not deployed to live provider accounts, and live acceptance remains to be recorded. See
  [Cloud and providers](../hosting/cloud.md).

## Where to follow along

Current and shipped work is tracked in the repository's
[issues](https://github.com/SpaceWorks-Labs/SpaceWorks/issues),
[pull requests](https://github.com/SpaceWorks-Labs/SpaceWorks/pulls) and release notes. To propose something,
open an issue, and see [Contributing](contributing.md).
