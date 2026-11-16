import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CardDesign } from "../../../../components/card-designer/cardTypes";
import { ArchivedDesigns, RemoveDesignButton } from "./DesignArchive";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../../lib/api")), staffRequest }));

const design = (patch: Partial<CardDesign>) => ({ id: 7, target_label: "Plan: Monthly", plan_id: 3, title_id: null,
  published_at: null, archived_at: null, can_edit: true, ...patch }) as CardDesign;

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  {node}</QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("card design archive (decision 219(h))", () => {
  it("archives a published override instead of deleting it", async () => {
    staffRequest.mockResolvedValue(design({ archived_at: "2026-11-09T10:00:00Z" }));
    const onRemoved = vi.fn();
    wrap(<RemoveDesignButton makerspaceId={4} design={design({ published_at: "2026-11-01T10:00:00Z" })} onRemoved={onRemoved} />);
    fireEvent.click(screen.getByRole("button", { name: "Archive design" }));
    fireEvent.click(await screen.findByRole("button", { name: "Archive" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/card-designs/7/archive", { method: "POST" }));
    await waitFor(() => expect(onRemoved).toHaveBeenCalled());
  });

  it("deletes an override that was never published", async () => {
    staffRequest.mockResolvedValue(undefined);
    wrap(<RemoveDesignButton makerspaceId={4} design={design({})} onRemoved={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete design" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/card-designs/7", { method: "DELETE" }));
  });

  it("lists archived designs and restores one", async () => {
    staffRequest.mockImplementation((path: string) => Promise.resolve(String(path).includes("archived=true")
      ? [design({ archived_at: "2026-11-09T10:00:00Z" })] : design({})));
    const onRestored = vi.fn();
    wrap(<ArchivedDesigns makerspaceId={4} canEdit onRestored={onRestored} />);
    expect(await screen.findByText("Archived designs (1)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/card-designs/7/unarchive", { method: "POST" }));
    await waitFor(() => expect(onRestored).toHaveBeenCalledWith(7));
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/card-designs?archived=true");
  });
});
