---
title: Security settings for your space
summary: Session lengths, idle timeout, unusual sign-in checks, CAPTCHA, passkeys and the staff network allow-list.
order: 50
keywords: security, session, idle timeout, captcha, ip allow-list, network, passkeys, risk check, remembered device, lock
---
**Security** holds the sign-in rules for your space. Each change asks you to confirm your identity and is recorded in the audit log.

## The settings

- **Check unusual sign-ins**: ask for an extra check on a new device or network. On by default.
- **Remember a checked device for (days)**: 1 to 90.
- **Staff session length (hours)**: how long a staff sign-in lasts, 1 to 720.
- **Staff idle timeout (minutes)**: sign staff out after inactivity; 0 turns it off.
- **CAPTCHA on sign-in**: **Off**, **After failed attempts** or **Always**. It works on your space's verified domain.
- **Allow passkeys**: on by default. Passkeys can't be made compulsory.
- **Staff IP allow-list**: networks staff may use the console from. Empty means any network.

## Change one

1. Open **Security**.
2. Enter the new value or choose an option, then press **Save**.
3. Confirm your identity when asked.

For the allow-list, type a network such as `203.0.113.0/24` under **Add a network**, press **Add**, then **Save list**. Make sure your own network is on it first.

![Screenshot: the Security page with Sign-in requirements](screenshot:sm-security)

## Platform locks

The platform administrator can lock a setting. A locked setting shows what it allows, and you can only make it stricter. Two-step sign-in for staff is a platform rule and always on.

## Personal data access

**Platform access to personal data** lists every time the platform administrator opened a window to see your space's personal details, with their reason.

> **Who can do this:** this space's Space Manager and the platform administrator. Security settings can't be handed to anyone else.
