---
title: The global member profile
group: How-to guides
order: 230
summary: One profile per account that every signed-in member can see by default, what goes on it, who sees what, and how the old per-space profiles were merged.
---

# The global member profile

Every person has **one profile for their whole account**, not one per space. It is addressed by their username, for example `/ada`, and reads like a short CV: who they are, what they have done and what they have built. This page explains what is on it, who can see it and what is never shown. Members edit it under **Account, Profile**; the member's own steps are in the [member user guide](../user-guides/member.md).

## Who sees it

| Viewer | What they see |
| --- | --- |
| The person | Everything, even sections switched off |
| Any signed-in member, in any space | The profile and the sections that are switched on |
| Someone who is not signed in | Nothing, unless the person turned on the **open web** switch |

- **Visible on the platform by default.** A profile is open to every signed-in user, like a username. The person can hide the whole profile, or any section.
- **The open web is a separate choice.** Letting logged-out visitors, search engines and share cards see the profile is off until the person turns it on and gives fresh consent. Turning it off takes it offline straight away.
- **A hidden profile looks like a missing one.** A hidden profile, one that does not exist and one belonging to a restricted or suspended account all give the same "not found", so nobody can tell them apart.

## What goes on a profile

Each item has its own show switch, and all start on.

- **Status.** A preset (Student, Working, Freelancing, Looking for work, Open to collaborate, Building a startup, Other) with an optional line of up to 120 characters.
- **About.** Headline, institution and a short bio.
- **Experience, education and volunteering.** Dated entries with a title, organisation, place and description. Volunteering follows the experience switch.
- **Achievements.** Two kinds, always labelled so a reader can tell them apart:
  - **Verified**: added by SpaceWorks from real records. These are placings and prizes from published hackathon results (including People's choice), roles such as judge, mentor or speaker, and events attended. Each says which space verified it.
  - **Self-reported**: things the person types in themselves (title, who issued it, date, link, description), always marked "self-reported".
- **Projects.** Projects the person types in, or a project imported from one of their own hackathon submissions, which copies the title, summary and links and stays linked back.
- **Skills, domains, links, interests and languages.** Links must start with `https://`.
- **Spaces and organizations.** Every space and organization the person is an active member of, with their role title when it is a standard one.
- **Vouched by.** People who vouched for them, shown as names only when those people also have a readable profile. Everyone else is counted, not named.
- **GitHub and the activity graph.** An optional daily-count graph of activity across the person's spaces (projects, events, and optionally speaking, machine jobs, bookings and loans), with a GitHub contribution calendar beside it when a GitHub username is entered. The graph shows counts only, never what happened.
- **Events attended and certifications**, built from the person's records.

## What is never shown

Whatever the switches say, a profile never shows:

- attendance at private, invite-only or unlisted events;
- results that are unpublished or withdrawn (a corrected result follows the latest publication);
- anything from a space where the person is restricted or suspended or their membership has been revoked, and a restricted or suspended account's profile is hidden entirely;
- email address, phone number or any other contact detail;
- spaces that the platform has hidden or archived (they are not named).

Roles and attendance from a space appear only when the viewer is allowed to see that space's information; published public hackathon results from any space may appear because they are already public.

A space's **member directory** is separate. It lists only that space's own members and shows just a name, headline and picture.

## Moving from per-space profiles

Earlier releases kept a profile for each membership. On upgrade, SpaceWorks builds one global profile per account from the most recently updated old profile and merges in the experience, projects, skills and links from the others, removing duplicates. The old rows are kept, read-only, and nothing is deleted in this release. Existing usernames keep working.

People whose profile had never been changed on purpose now get the new default (visible on the platform) and receive a one-time in-app notice that links to their profile settings. Anyone who had deliberately hidden their profile keeps it hidden.

## For operators

- The profile belongs to the **account**, not to a space. It travels with an account export and with the account if it is merged, and a space move carries only that space's directory entries.
- Profiles are part of the Membership area (`membership` module), which lists them under join requests, referrals, profiles, directory and cards. See [Memberships](../modules/memberships.md#the-global-member-profile).
- The profile address is the member's **username**; see [Usernames](usernames.md).

## See also

- [Usernames](usernames.md)
- [Memberships](../modules/memberships.md)
- [Let people check in by location](presence-check-in.md) for how profiles appear in "Here now"
