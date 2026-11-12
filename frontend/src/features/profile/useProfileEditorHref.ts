/** The profile is global, so the editor is one place for everyone: no per-makerspace lookup is needed any more. */
export const PROFILE_EDITOR_HREF = "/member/profile";

/** Ownership comes from the profile response's `audience`; an owner always edits at /member/profile. */
export function useProfileEditorHref(owner: boolean) {
  return { href: owner ? PROFILE_EDITOR_HREF : undefined };
}
