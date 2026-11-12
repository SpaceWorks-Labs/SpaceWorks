import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";

const { blob } = vi.hoisted(() => ({ blob: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...await original<object>(), memberRequestBlob: blob }));

import { DesignedTicket } from "./DesignedTicket";

const wrap = (ui: import("react").ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
const fallback = <p>Generic ticket card</p>;

beforeEach(() => {
  blob.mockReset();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:ticket"), revokeObjectURL: vi.fn() }));
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("designed ticket on the ticket page (parity D17)", () => {
  it("shows the space's designed ticket for a confirmed, unused place", async () => {
    blob.mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    render(wrap(<DesignedTicket registrationId={41} eventTitle="Robot night" enabled fallback={fallback} />));
    expect(await screen.findByRole("img", { name: "Your ticket for Robot night, with your check-in code" })).toHaveAttribute("src", "blob:ticket");
    expect(blob).toHaveBeenCalledWith("/member/event-registrations/41/ticket?format=png");
    expect(screen.queryByText("Generic ticket card")).toBeNull();
    expect(screen.getByRole("button", { name: "Download ticket PDF" })).toBeVisible();
  });

  it("is hidden once checked in: nothing is fetched and the generic card shows", () => {
    render(wrap(<DesignedTicket registrationId={41} eventTitle="Robot night" enabled={false} fallback={fallback} />));
    expect(screen.getByText("Generic ticket card")).toBeVisible();
    expect(screen.queryByRole("img")).toBeNull();
    expect(blob).not.toHaveBeenCalled();
  });

  it("falls back when the server refuses a used ticket (410) or has no design (404)", async () => {
    blob.mockRejectedValue(new StructuredApiError(410, { code: "ticket_used", detail: "Checked in." }));
    render(wrap(<DesignedTicket registrationId={41} eventTitle="Robot night" enabled fallback={fallback} />));
    await waitFor(() => expect(blob).toHaveBeenCalled());
    expect(await screen.findByText("Generic ticket card")).toBeVisible();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("removes a shown ticket when the place is checked in while the page is open", async () => {
    blob.mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    const view = render(wrap(<DesignedTicket registrationId={41} eventTitle="Robot night" enabled fallback={fallback} />));
    await screen.findByRole("img");
    view.rerender(wrap(<DesignedTicket registrationId={41} eventTitle="Robot night" enabled={false} fallback={fallback} />));
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("Generic ticket card")).toBeVisible();
  });
});
