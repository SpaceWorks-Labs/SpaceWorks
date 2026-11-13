import { t } from "@lingui/core/macro";

export type ColourPreset = { id: string; name: string; primary: string; accent: string };

/** Brand-safe starting points. Every one passes the backend contrast rules and the 3:1 fill-on-page advice in both modes. */
export function colourPresets(): ColourPreset[] {
  return [
    { id: "default", name: t`Space Works default`, primary: "", accent: "" },
    { id: "orange", name: t`Workshop Orange`, primary: "#c2410c", accent: "#c2410c" },
    { id: "ocean", name: t`Ocean blue`, primary: "#1d5fa8", accent: "#1d5fa8" },
    { id: "forest", name: t`Forest green`, primary: "#2f7d46", accent: "#2f7d46" },
    { id: "plum", name: t`Plum`, primary: "#9a3f88", accent: "#9a3f88" },
    { id: "slate", name: t`Slate`, primary: "#5b6573", accent: "#5b6573" },
  ];
}
