import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { MemberCardPanel } from "./MemberCardPanel";
import { readOfflineCard, saveOfflineCard } from "./memberCard/offlineCard";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest: request }));

function show(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(<QueryClientProvider client={client}><MemberCardPanel makerspaceId={5} /></QueryClientProvider>);
}

beforeEach(() => { request.mockReset(); localStorage.clear(); window.history.replaceState(null, "", "/member"); });
afterEach(() => { localStorage.clear(); window.history.replaceState(null, "", "/"); });

describe("member card loading and module withdrawal", () => {
  it("announces loading before any QR or editor is available", () => {
    request.mockReturnValue(new Promise(() => {}));
    show();
    expect(screen.getByText("Loading your card…")).toBeVisible();
    expect(screen.queryByRole("img", { name: "Your member card QR code" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Name printed on the card")).not.toBeInTheDocument();
  });

  it("a failed initial read announces the error and exposes no card controls", async () => {
    request.mockRejectedValue(new Error("Connection lost"));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection lost");
    expect(screen.queryByRole("button", { name: "Save name" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Preview card (PDF)" })).not.toBeInTheDocument();
  });

  it.each(["module_disabled", "feature_disabled", "not_found"])("a 404 %s erases the offline bearer QR", async code => {
    saveOfflineCard({ id: 3, name: "Member", number: 103, space: "Lab", qr: "data:image/png;base64,eA==",
      savedAt: "2026-11-01T00:00:00Z" });
    expect(readOfflineCard()?.id).toBe(3);
    request.mockRejectedValue(new StructuredApiError(404, { code, detail: "Unavailable" }));
    show();
    expect(await screen.findByText("No card issued yet. Ask the front desk for your member card.")).toBeVisible();
    expect(readOfflineCard()).toBeNull();
    expect(screen.queryByRole("img", { name: "Your member card QR code" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save card for offline use" })).not.toBeInTheDocument();
  });
});
