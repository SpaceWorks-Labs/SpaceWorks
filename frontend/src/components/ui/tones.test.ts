import { describe, expect, it } from "vitest";
import { toneClasses, toneMarkClasses, toneSurfaceClasses } from "./tones";

describe("tone classes", () => {
  it("draws status marks as solid brand fills in both modes (brand p.16)", () => {
    for (const classes of Object.values(toneMarkClasses)) expect(classes).not.toMatch(/dark:/);
    expect(toneMarkClasses.success).toBe("border-transparent bg-success text-on-success");
    expect(toneClasses).toBe(toneMarkClasses);
  });
  it("keeps large tinted areas soft in dark mode", () => {
    for (const tone of ["success", "warn", "info"] as const) {
      expect(toneSurfaceClasses[tone]).toContain(`dark:bg-${tone}-soft`);
      expect(toneSurfaceClasses[tone]).toContain(`dark:text-${tone}-ink`);
    }
    expect(toneSurfaceClasses.danger).toBe(toneMarkClasses.danger);
  });
});
