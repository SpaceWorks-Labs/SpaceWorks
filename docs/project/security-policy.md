---
title: Security policy
group: Project
order: 30
summary: How to report a vulnerability privately, what to include, and which versions receive fixes.
---

# Security policy

## Reporting a vulnerability

Please report suspected security vulnerabilities **privately**. Do not open a public GitHub issue for a
vulnerability, and do not post exploit details in a public pull request, discussion or chat.

The repository's `SECURITY.md` asks for reports by email to
[shaanshoukath4522@gmail.com](mailto:shaanshoukath4522@gmail.com). You can also open a private report on the
repository's GitHub security advisories page:
<https://github.com/SpaceWorks-Labs/SpaceWorks/security/advisories>. If private reporting is not enabled
there when you look, use the email.

Include:

- the affected version or commit (an installed server records its version in
  `.spaceworks-version` in the install directory);
- steps to reproduce the issue;
- its potential impact, including whether it crosses from one makerspace into another.

You will get a best-effort acknowledgement within a few days. The maintainers coordinate remediation and
disclosure with you. Please give them a reasonable chance to fix the problem before you publish.

## Supported versions

Security fixes land on the latest release and on `main`. Support for older tags is best effort. Upgrades only
move forward, so the way to receive a fix is to update to the latest release; see
[Upgrades](../hosting/upgrades.md).

## What counts

Anything that breaks the guarantees the product makes is worth reporting. Examples:

- reading or changing another makerspace's data (a cross-tenant leak);
- bypassing sign-in, MFA, role checks or the control-plane restrictions;
- exposing evidence photos, private files or stored secrets;
- tampering with audit logs or evidence records that are meant to be immutable;
- remote code execution, injection, request forgery or similar flaws in the API or website.

## Keeping your own server safe

Most real-world risk is in how a server is run rather than in the code. Read
[Security hardening](../hosting/security.md): use HTTPS, enrol MFA, keep the control plane server-only,
protect your `.env` and encryption keys, and keep a verified off-server backup.

The maintainers also record what was verified for each release, including known image findings and the
risk notes behind them. See the [0.12.0 security summary](../security-summary-0.12.0.md).
