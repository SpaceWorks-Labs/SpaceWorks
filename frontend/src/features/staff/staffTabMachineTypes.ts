// --- machine-type subpages -------------------------------------------------------------
//
// THE ID IS AUTHORITATIVE AND THE SLUG IS DECORATION. Machine-type slug uniqueness is only
// SCOPED -- `uniq_global_machinetype_slug` among globals, `uniq_lab_machinetype_slug` per
// makerspace -- so a makerspace may legally own a local type slugged `3d_printer` while the
// global built-in of that slug also exists, and both appear in one console. Three shipped
// surfaces have already served one type's jobs under another by keying on the slug. The
// slug rides along only so the URL is readable.

export function machineTypeSegment(machineType: { id: number; slug?: string | null }) {
  const slug = (machineType.slug ?? "").trim();
  return slug ? `${machineType.id}-${slug}` : String(machineType.id);
}

export function parseMachineTypeSegment(segment: string): number | null {
  // Leading integer only. A malformed segment is `null` -- "no type selected", i.e. the
  // index -- and never a silent fall-through to some default type.
  const match = /^(\d+)/.exec(segment.trim());
  if (!match) return null;
  const id = Number(match[1]);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
