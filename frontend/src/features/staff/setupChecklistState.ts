import { t } from "@lingui/core/macro";
export type SetupState = {
  profile_set: boolean; logo_set?: boolean; hours_set: boolean; first_item_added: boolean; staff_invited: boolean; modules_chosen: boolean;
};
export function setupSteps(state: SetupState, modules: readonly string[]) {
  return [
    // `section` deep-links a Settings subpage (/admin/settings/<section>).
    { key: "profile_set", label: t`Add your address`, tab: "settings", section: "general" },
    // Older servers do not send logo_set; the step is then left out rather than shown as never done.
    ...(state.logo_set === undefined ? [] : [{ key: "logo_set", label: t`Add your logo`, tab: "settings", section: "branding" }]),
    { key: "hours_set", label: t`Set opening hours`, tab: "settings", section: "general" },
    ...(modules.includes("public_inventory") ? [{ key: "first_item_added", label: t`Add your first item`, tab: "inventory" }] : []),
    { key: "staff_invited", label: t`Invite staff`, tab: "users" },
    { key: "modules_chosen", label: t`Choose what your space runs`, tab: "modules" },
  ].map(step => ({ ...step, complete: state[step.key as keyof SetupState] === true }));
}
