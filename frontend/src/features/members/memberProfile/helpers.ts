export const tagsToText = (values: string[]) => values.join(", ");
export const textToTags = (value: string) =>
  value.split(",").map((item) => item.trim()).filter(Boolean);

const PROFILE_TONES = [
  "border-accent bg-accent-soft",
  "border-brand bg-brand-soft",
  "border-success bg-success-soft",
  "border-warn bg-warn-soft",
] as const;

export function profileToneForIdentity(identity: string | number | undefined) {
  if (identity === undefined || identity === "") return "border-brand bg-brand-soft";
  const total = [...String(identity)].reduce((sum, character) => sum + character.codePointAt(0)!, 0);
  return PROFILE_TONES[total % PROFILE_TONES.length];
}
