import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { AccountProfile } from "../accountProfileTypes";
import { VisibilityPanel } from "./VisibilityPanel";

vi.mock("./HandleField", () => ({ HandleField: ({ handle }: { handle: string | null }) => <span>{handle}</span> }));
vi.mock("./SectionToggle", () => ({ SectionToggle: () => null }));
vi.mock("./ProfilePreviewDialog", () => ({ ProfilePreviewDialog: () => null }));

describe("publication controls retired by decision 549", () => {
  it("has no visibility toggle or consent prompt, even for stored legacy opt-outs", () => {
    const profile = { handle: "maker.name", is_visible: false, public_visible: false,
      public_reconfirm_pending: true } as AccountProfile;
    render(<MemoryRouter><VisibilityPanel profile={profile} /></MemoryRouter>);
    expect(screen.getByText("Public profile")).toBeVisible();
    expect(screen.getByRole("link", { name: "View public profile" })).toHaveAttribute("href", "/@maker.name");
    expect(screen.queryAllByRole("switch")).toHaveLength(0);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.queryByText("Confirm the open web again.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Publish on the open web" })).toBeNull();
  });

  it("keeps handle choice available without claiming a profile URL", () => {
    render(<MemoryRouter><VisibilityPanel profile={{ handle: null } as AccountProfile} /></MemoryRouter>);
    expect(screen.queryByRole("link", { name: "View public profile" })).toBeNull();
    expect(screen.queryAllByRole("switch")).toHaveLength(0);
  });
});
