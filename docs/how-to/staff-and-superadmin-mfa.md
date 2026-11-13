---
title: Two-step sign-in for staff and superadmins
group: How-to guides
order: 60
summary: Enrol an authenticator or passkey, understand the staff grace period and recover a locked-out account.
---

# Two-step sign-in for staff and superadmins

Two-step sign-in (MFA) uses an authenticator app (TOTP) or a passkey. It is **mandatory** for anyone who holds a staff role, and optional for everyone else.

## The rules

- Every person with a staff role, organization authority or a resource grant must hold a second factor. This does not depend on the platform switch, which only governs member opt-in.
- A person with staff authority but no factor can still sign in and use member features. Staff routes refuse them once their **three-day grace** has ended.
- The platform superadmin is exempt from this staff floor. The server-side control plane (`/control/`) keeps its own TOTP step when the superadmin has enrolled one or platform policy requires it.
- Passkeys are offered, never forced.

## Enrol (any person)

1. Open `/mfa` (the **Account security** page), or the same section in your account.
2. Under **Authenticator app**, scan the code with your authenticator and enter the first code.
3. Save the **recovery codes** shown. Each works once.
4. Optionally add a **Passkey**. Removing the passkey your browser used signs you out.

## See who is not enrolled yet

On the server:

```bash
python manage.py staff_mfa_readiness
```

It lists elevated accounts with no second factor, per space, and their reset path.

## Reset someone's second factor

A Space Manager or platform admin can start a reset from **Staff & roles**. From the server, a superadmin can run:

```bash
python manage.py reset_mfa <username> --reason "Lost phone, identity checked in person"
```

The reason (3 to 300 characters) is audited.

## A superadmin is locked out

If the only superadmin loses their authenticator, run on the server:

```bash
python manage.py recover_superadmin <username> --reset-mfa
```

It discards the lost authenticator; the account then signs in with its password until it enrols again. Add `--password` to set one explicitly; without it the command generates one.

## Sign-in blocks and IP rules

The same host tooling can list or lift automatic sign-in blocks:

```bash
python manage.py login_security --list
python manage.py login_security --unblock <ip>
python manage.py login_security --allow <cidr> --note "Office"
```

> **Warning** Do not turn platform MFA off to fix one person's lockout. Reset that person instead; the audit log records who did it and why.

## See also

- [Choose and configure sign-in methods](sign-in-methods.md)
- [Command reference](../reference/commands.md)
