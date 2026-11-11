import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { MakerspacePicker } from "../features/staff/MakerspacePicker";
import { HubFooter } from "../features/hub/HubFooter";
import { nounOf, nounTitleOf, spaceKindOf } from "./spaceNoun";

const hosting = vi.hoisted(() => ({ enabled: false }));
vi.mock("../features/hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: hosting.enabled }) }));
vi.mock("../features/organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => false }));

describe("space nouns (decision 295)", () => {
  it("treats anything but an explicit organization as a makerspace", () => {
    expect(spaceKindOf(undefined)).toBe("makerspace");
    expect(spaceKindOf({ kind: "makerspace" })).toBe("makerspace");
    expect(spaceKindOf({ space_noun: "organization" })).toBe("organization");
    expect(nounOf({ kind: "organization" })).toBe("organization");
    expect(nounTitleOf({})).toBe("Makerspace");
  });

  it("words the space picker neutrally once organization workspaces are listed", () => {
    const space = (id: number, kind?: "organization") => ({ id, name: `Space ${id}`, slug: `s${id}`, public_code: `S00${id}`,
      telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false, ...(kind ? { kind } : {}) });
    const { rerender } = render(<MemoryRouter><MakerspacePicker person makerspaces={[space(1)]} loading={false} username="asha" onSelect={vi.fn()} onSignOut={vi.fn()} /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Choose a makerspace" })).toBeInTheDocument();
    expect(screen.getByText("S001 · Operate this makerspace →")).toBeInTheDocument();
    rerender(<MemoryRouter><MakerspacePicker person makerspaces={[space(1), space(2, "organization")]} loading={false} username="asha" onSelect={vi.fn()} onSignOut={vi.fn()} /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Choose a space" })).toBeInTheDocument();
    expect(screen.getByText("S002 · Operate this organization →")).toBeInTheDocument();
  });

  it("links the hub footer to the request form only while requests are open", () => {
    const show = () => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><HubFooter /></MemoryRouter></QueryClientProvider>);
    const first = show();
    expect(screen.queryByRole("link", { name: "Request a workspace" })).not.toBeInTheDocument();
    first.unmount();
    hosting.enabled = true;
    show();
    expect(screen.getByRole("link", { name: "Request a workspace" })).toHaveAttribute("href", "/hosting");
  });
});
