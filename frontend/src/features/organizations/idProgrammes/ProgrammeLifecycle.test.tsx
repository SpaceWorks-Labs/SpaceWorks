import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Programme } from "./api";
import { ProgrammeArchivedBanner, RemoveProgramme } from "./ProgrammeLifecycle";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const programme = (patch: Partial<Programme> = {}) => ({ id: 11, name: "Student ID", status: "active", can_manage: true,
  archived_at: null, counts: { all: 0, pending: 0, approved: 0, rejected: 0, revoked: 0 }, ...patch }) as Programme;
const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  {node}</QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("ID programme archive (decision 219(h))", () => {
  it("deletes a programme that never approved a card and goes back to the list", async () => {
    staffRequest.mockResolvedValue(undefined);
    const onDeleted = vi.fn();
    wrap(<RemoveProgramme programme={programme({ counts: { all: 2, pending: 2, approved: 0, rejected: 0, revoked: 0 } })} onDeleted={onDeleted} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete programme" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/id-programmes/11", { method: "DELETE" }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });

  it("archives a programme with issued cards instead", async () => {
    staffRequest.mockResolvedValue(programme({ archived_at: "2026-11-09T10:00:00Z", status: "closed" }));
    const onDeleted = vi.fn();
    wrap(<RemoveProgramme programme={programme({ counts: { all: 3, pending: 0, approved: 2, rejected: 0, revoked: 1 } })} onDeleted={onDeleted} />);
    expect(screen.queryByRole("button", { name: "Delete programme" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Archive programme" }));
    fireEvent.click(await screen.findByRole("button", { name: "Archive" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/id-programmes/11/archive", { method: "POST" }));
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("shows an archived banner with Restore for managers", async () => {
    staffRequest.mockResolvedValue(programme());
    wrap(<ProgrammeArchivedBanner programme={programme({ archived_at: "2026-11-09T10:00:00Z", status: "closed" })} />);
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/id-programmes/11/unarchive", { method: "POST" }));
  });

  it("hides Restore from viewers and renders nothing when not archived", () => {
    const { container, rerender } = wrap(<ProgrammeArchivedBanner programme={programme()} />);
    expect(container.textContent).toBe("");
    rerender(<QueryClientProvider client={new QueryClient()}>
      <ProgrammeArchivedBanner programme={programme({ archived_at: "2026-11-09T10:00:00Z", can_manage: false })} /></QueryClientProvider>);
    expect(screen.getByText("Archived")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Restore" })).toBeNull();
  });
});
