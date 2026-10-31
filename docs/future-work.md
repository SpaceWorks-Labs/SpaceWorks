# Roadmap and further work

Ongoing work is focused on reliable self-hosting and complete makerspace operations:

- automatic, backup-first deployment from published `main` releases;
- stable public, member, staff, and superadmin workflows across the full module set;
- continued accessibility, mobile, reporting, and operational resilience work.

## Further work

The [module list](choosing-modules.md#every-module-by-area) describes implemented registry keys. Further
hardware integration and invitation request improvements are tracked separately:

- **Hardware integration** — Connected devices already supplies signed device identity, printer
  reports and label commands. Broader CNC/controller and door/access-control integrations remain
  further work; self check-in requires an in-range browser location, which remains spoofable.
  Device-reported state still needs authenticated, scoped workflow enforcement.
- **Invitation requests** — prospective members can already request invitations as well as receive
  staff invitations or apply to join. Further work belongs in the issue tracker, not as an unbuilt
  module key.

Current work and shipped changes are tracked in
[GitHub issues](https://github.com/SpaceWorks-Labs/SpaceWorks/issues),
[pull requests](https://github.com/SpaceWorks-Labs/SpaceWorks/pulls), and the release notes. The running
product intentionally does not expose a separate roadmap page.
