---
title: Usernames
group: How-to guides
order: 240
summary: Every account has a username that is also its profile address. How it is chosen at sign-up, what happens to older accounts, and which names are reserved.
---

# Usernames

Every SpaceWorks account has a **username**, also called a handle. It is the person's profile address (`/ada`), the name used for links to them, and the way other members can find them across spaces. Nobody can use the platform without one.

## The rules

- 3 to 30 characters: lowercase letters, numbers, dots, underscores and hyphens.
- It must start and end with a letter or a number.
- It must not be taken, and must not be a **reserved name** (below).
- Letter case does not matter: `Ada` and `ada` are the same name.

A person can change their username once every 30 days. After a change, the old address keeps pointing to the new one for 30 days, and nobody else can claim the old name during that time. A username chosen automatically leaves one free change without the wait.

## How a person gets one

### At sign-up

The create-account form asks for a username. It is **pre-filled with the best available suggestion** and checks availability while the person types, showing whether the name is invalid, reserved or taken. The suggestion comes from the account username if one exists, then the display name turned into a short slug, then the slug plus digits. If the person leaves the field alone, the suggestion is used.

This applies to every way of signing up: email and password, one-time code, Google, GitHub and Apple sign-in, a walk-in record that is upgraded to an account, and the accounts created through staff or organization invitations. Invitations never make an account themselves; they attach to one that already exists, so the account got its username by one of the other routes.

If the chosen name is taken at the same moment by someone else, sign-up fails with a clear message and **no account is created**, so nobody ends up with half an account.

### After sign-in with a social account

A social sign-in has no form, so the account is created with the best suggestion already claimed. Right after signing in the person sees **"Your username is X, change it?"** and can keep it or pick another. This step can be dismissed.

### Accounts that existed before usernames were required

When SpaceWorks is upgraded, each existing account keeps its old username as its handle whenever that name is valid and free. For most people nothing happens.

Anyone left without one sees a full-screen **"Choose your username"** step the next time they sign in, with a suggestion filled in, so accepting it takes one tap. It cannot be skipped and has no close button; signing out still works. Until it is done, every action that changes something is refused with "Choose your username before continuing", but reading pages still works.

Native apps and API clients receive the same information in the sign-in response (`handle_required` and a suggested name) and the same refusal, so they can show the same step.

### Who is not affected

Machine API clients, kiosk and station tokens, display screens, walk-in records and platform administrator accounts are never asked for a username.

## Reserved names

A username can never be the same as an address the site already uses. The list covers the main sections and system routes, for example `admin`, `api`, `docs`, `help`, `m`, `member`, `events`, `shop`, `spaces`, `features`, `display`, `privacy`, `terms`, `security`, `oauth`, `pay`, `scanner`, `kiosk`, `stats`, `verify` and similar. The check says "reserved" when a name is on it.

## For operators

- The availability check is a public, rate-limited route (`GET /api/v1/handles/check`), described in the API reference. It is advisory; the claim itself is checked again under a lock.
- To see how the username turns into a profile address, read [The global member profile](member-profile.md).

## See also

- [The global member profile](member-profile.md)
- [Choose and configure sign-in methods](sign-in-methods.md)
