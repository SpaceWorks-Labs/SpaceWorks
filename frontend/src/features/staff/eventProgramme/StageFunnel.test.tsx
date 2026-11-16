import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import { StageFunnel } from "./StageFunnel";

describe("stage funnel (S16)", () => {
  it("shows counts per stage, with a dash where there is no shortlist", async () => {
    const { container } = render(<StageFunnel rows={[
      { position: 1, name: "Idea", submitted: 40, eligible: 36, shortlisted: 12, advanced: 11 },
      { position: 2, name: "Final", submitted: 11, eligible: 9, shortlisted: null, advanced: null }]} />);
    expect(screen.getByRole("rowheader", { name: "1. Idea" })).toBeTruthy();
    expect(screen.getByText("36")).toBeTruthy();
    expect(screen.getAllByText("\u2014")).toHaveLength(2);
    await expectNoA11yViolations(container);
  });
});
