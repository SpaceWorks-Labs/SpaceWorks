import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { brandContrastReport } from "../../../lib/brandColours";
import type { Makerspace } from "../StaffPanels";

export type Look = "light" | "dark" | "system";
type Colours = { primary: string; accent: string; mode: Look };
const LOOKS: readonly string[] = ["light", "dark", "system"];
const SHARED_KEYS = ["makerspaces", "member", "runtime-tenant", "runtime-tenant-origin", "public-makerspaces"];

/** Draft colours, the same contrast verdict the API applies, save, and a one-step undo of the last save. */
export function useColourDraft(makerspace: Makerspace, settings: Makerspace | undefined) {
  const queryClient = useQueryClient();
  const saved = settings?.theme_config ?? {};
  const savedPrimary = typeof saved.primary_color === "string" ? saved.primary_color : "";
  const savedAccent = typeof saved.accent_color === "string" ? saved.accent_color : "";
  const savedMode = (LOOKS.includes(saved.mode) ? saved.mode : "light") as Look;
  const [draft, setDraft] = useState<Colours>({ primary: savedPrimary, accent: savedAccent, mode: savedMode });
  const [undo, setUndo] = useState<Colours | null>(null);
  useEffect(() => { setDraft({ primary: savedPrimary, accent: savedAccent, mode: savedMode }); }, [makerspace.id, savedPrimary, savedAccent, savedMode]);
  useEffect(() => { setUndo(null); }, [makerspace.id]);
  const theme = { ...saved, mode: draft.mode, primary_color: draft.primary.trim(), accent_color: draft.accent.trim() };
  const report = brandContrastReport(theme);
  const blocked = !report.valid || report.failures.length > 0;
  const dirty = theme.primary_color !== savedPrimary || theme.accent_color !== savedAccent || draft.mode !== savedMode;
  const mutation = useMutation({
    mutationFn: (input: { id: number; slug: string; colours: Colours }) => staffRequest<Makerspace>(`/admin/makerspaces/${input.id}`, {
      method: "PATCH", body: JSON.stringify({ theme_config: { ...saved, mode: input.colours.mode, primary_color: input.colours.primary, accent_color: input.colours.accent } }),
    }),
    onSuccess: (_result, input) => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", input.id] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["tenant-bootstrap", input.slug] });
      for (const key of SHARED_KEYS) void queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  const { reset } = mutation;
  useEffect(() => { reset(); }, [makerspace.id, reset]);
  const save = () => {
    if (!settings || blocked || !dirty || mutation.isPending) return;
    const before = { primary: savedPrimary, accent: savedAccent, mode: savedMode };
    mutation.mutate({ id: makerspace.id, slug: makerspace.slug, colours: { primary: theme.primary_color, accent: theme.accent_color, mode: draft.mode } },
      { onSuccess: () => setUndo(before) });
  };
  const undoSave = () => {
    if (!undo || mutation.isPending) return;
    mutation.mutate({ id: makerspace.id, slug: makerspace.slug, colours: undo }, { onSuccess: () => setUndo(null) });
  };
  return { draft, setDraft, theme, report, blocked, dirty, mutation, save, undoSave, canUndo: Boolean(undo) && !dirty,
    discard: () => setDraft({ primary: savedPrimary, accent: savedAccent, mode: savedMode }) };
}
