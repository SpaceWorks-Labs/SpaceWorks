import { t } from "@lingui/core/macro";
import { IdCard, Smartphone, Tv, UserRound } from "lucide-react";
import type { CataloguePart } from "./types";

/** Membership and Mobile groups. */
export const membershipAndMobile = (): CataloguePart => ({
  membership: { icon: IdCard, value: t`Plans, renewals and custom ID cards.`,
    what: t`Join requests, membership plans and automatic renewal, waivers, referrals and a consent-based member directory, and Card Studio for member cards, staff ID cards and certificates: layers, snapping, rulers, icons and shapes, your space's colours and picture library, cut-out photos, numbering, print-ready PDFs with bleed and crop marks, bulk sheets and cards from a CSV, desk printing at card size, wallet passes and a public check page.`,
    roles: [t`Space managers`, t`Members`, t`Front-desk staff`],
    
    
    
    integrations: [t`Apple and Google wallet passes`, t`Background eraser for card photos`, t`Online payments`, t`Card printers`],
    newIn: [t`Card Studio with certificates`, t`Print-ready card PDFs with bleed and crop marks`, t`Background eraser adapter for ID photos`, t`Wallet passes with a public check page`] },
  member_accounts: { icon: UserRound, value: t`Sign-in, profiles and the member area.`,
    what: t`One global profile per account, with a required username, visible to signed-in members by default and a separate switch for the open web. Share verified and self-reported achievements, projects, experience and education. The membership module adds the member dashboard with request and returned-item history, fees, outstanding money per currency and personal notices. Staff keep their own password sign-in and mandatory second factor.`,
    roles: [t`Members`], 
    noLimits: t`Sign-in accounts are counted by the members limit.`,
    integrations: [t`Google and other social sign-in`, t`Phone sign-in`, t`Passkeys`], newIn: [t`Global profiles and usernames`] },
  presence: { icon: Tv, value: t`Who is here now, and a screen to show it.`,
    what: t`Time-limited check-in, a public who-is-here page and paired display screens, with Anthias players for signage.`,
    roles: [t`Members`, t`Front-desk staff`], 
    integrations: [t`Anthias digital signage`, t`Paired TV displays`, t`Geofenced check-in`],
    newIn: [t`Space display and Anthias playlists`] },
  mobile: { icon: Smartphone, value: t`Attested device sessions and native push.`,
    what: t`Released Android and iOS apps use device sessions that prove the app is genuine, native push and the optional in-app payment sheet. Staff access is a verified step-up on the same person account.`,
    roles: [t`Members`], 
    integrations: [t`Firebase and Apple push`, t`In-app payment sheet`] },
});
