---
title: Admit minors with guardian consent
group: How-to guides
order: 170
summary: Turn on minors, set ages and what they may do, and understand how consent is recorded and expires.
---

# Admit minors with guardian consent

When minors are admitted, a person under the adult age needs a guardian's signed consent before they join, register for an event, take a guest pass, check in on site, borrow or use machines, as far as your settings allow.

## Before you start

- **Membership** is on.
- Switch on **Minors** (`membership.minors`) in **Settings > Areas > Features**.
- You are the Space Manager.
- Consider enabling [scoped PII encryption](../scoped-pii-encryption.md): when on, the minor's birth date and the guardian's contact are stored encrypted.

## Steps

1. Open **Settings > People > Community**.
2. Under **Minors**, tick **Admit people under the adult age**, then set the **Minimum age** and the **Adult age** (age of majority).
3. Under **What minors may do**, choose:
   - **A guardian must be checked in with them**;
   - **Minors may borrow items**;
   - **Minors may use machines**;
   - **Consent valid for** a number of days, after which the guardian signs again.
4. Save. Changes apply to new consents and checks.

## What happens at the desk and online

- A minor is recorded with a birth date or an "under age" declaration, and a guardian's contact.
- The guardian e-signs a versioned consent, in the same way a waiver is versioned. Until it is valid, the action is refused with a code such as `guardian_consent_required`.
- Consent lapses after the number of days you set.
- Door access is not part of this feature.

## Volunteer credit and join follow-up

The same page holds **Volunteer credit** (approved volunteer minutes turn into a discount or free days on the next membership charge; 0 minutes turns it off) and **Join follow-up** (one opt-in invitation to non-member event attendees after the event). Each appears only when its own switch is on.

> **Note** Turning minors off hides the surface and keeps the data. A purge by the superadmin deletes minor records, consents and consent texts, and cannot be undone.

## Verify

Register a test minor with a test guardian email and try to borrow or check in before consent is signed: the action must be refused with the consent message, then succeed after the guardian signs.

## See also

- [Set up guest passes and waivers](guest-passes-and-waivers.md)
- [Module guide](../MODULES.md) (`membership.minors`)
