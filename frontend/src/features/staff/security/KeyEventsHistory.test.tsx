import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KeyEventsHistory } from "./KeyEventsHistory";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <KeyEventsHistory makerspaceId={7} /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("KeyEventsHistory", () => {
  it("lists rotations from the paginated key-events feed", async () => {
    staffRequest.mockResolvedValue({ count: 1, results: [{ id: 1, kind: "dek_rotation", status: "completed", from_version: 1, to_version: 2,
      rows_done: 40, rows_skipped: 0, retained_versions: [1], error_code: "", started_at: "2026-11-01T10:00:00Z",
      updated_at: "2026-11-01T10:05:00Z", completed_at: "2026-11-01T10:05:00Z" }] });
    show();
    expect(await screen.findByText(/dek rotation · version 1 → 2/)).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/security/key-events?page=1");
  });

  it("says so when nothing has run", async () => {
    staffRequest.mockResolvedValue({ count: 0, results: [] });
    show();
    expect(await screen.findByText("No key rotations have run for this space yet.")).toBeInTheDocument();
  });
});
