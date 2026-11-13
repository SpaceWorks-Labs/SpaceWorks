import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { SheetPreviewDialog } from "../../features/cards/SheetPreviewDialog";
import type { CardDesign, CardTemplate } from "./cardTypes";
import { doc, layer } from "./designerFixtures.test";
import { HistoryPanel } from "./HistoryPanel";
import { TemplateGallery } from "./TemplateGallery";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), ...api }));

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const design = { id: 1, domain: "member_cards", name: "Default", revision: 5, document: doc([layer()]) } as unknown as CardDesign;
const body = (call: unknown[]) => JSON.parse(String((call[1] as RequestInit).body));

beforeEach(() => { api.staffRequest.mockReset(); api.staffRequestBlob.mockReset(); window.localStorage.setItem("spaceworks.card-studio-mode", "advanced"); });

describe("template gallery", () => {
  const template = (key: string, label: string, theme: "light" | "dark"): CardTemplate => ({ key, label, theme,
    document: doc([layer({ kind: "data_field", field: "name", text: "{{name}}", colour: theme === "dark" ? "#FFFFFF" : "#142C2A" })]) });

  it("switches light and dark and resets the draft to the chosen template", async () => {
    api.staffRequest.mockImplementation(async (path: string) => {
      if (path.endsWith("/templates")) {
        return [template("classic", "Classic", "light"), template("classic", "Classic", "dark"), template("bold", "Bold", "light"),
          template("bold", "Bold", "dark")];
      }
      if (path.endsWith("/reset")) return { ...design, revision: 6 };
      throw new Error(`unexpected ${path}`);
    });
    const onAdopt = vi.fn();
    wrap(<TemplateGallery design={design} values={{ name: "Priya Raman" }} onAdopt={onAdopt} onError={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /templates/i }));
    expect(await screen.findByRole("img", { name: "Classic, light, front" })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Classic, dark, front" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
    expect(await screen.findByRole("img", { name: "Classic, dark, front" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use Bold" }));
    fireEvent.click(await screen.findByRole("button", { name: "Replace the draft" }));
    await waitFor(() => expect(onAdopt).toHaveBeenCalledWith(expect.objectContaining({ revision: 6 })));
    const reset = api.staffRequest.mock.calls.find((call) => String(call[0]).endsWith("/reset"))!;
    expect(reset[0]).toBe("/admin/card-designs/1/reset");
    expect(body(reset)).toEqual({ template: "bold", theme: "dark" });
  });
});

describe("version history", () => {
  const page = { count: 2, next: null, previous: null, results: [
    { revision: 5, created_at: "2026-11-05T10:00:00Z", created_by: "Asha", is_current: true, is_published: false, review: "", layers: 3 },
    { revision: 3, created_at: "2026-11-01T10:00:00Z", created_by: "Bo", is_current: false, is_published: true, review: "approved", layers: 2 },
  ] };
  function mockHistory(restore: () => unknown) {
    api.staffRequest.mockImplementation(async (path: string) => {
      if (path.includes("/revisions?page=")) return page;
      if (path.endsWith("/revisions/3")) return { ...page.results[1], document: doc([layer()]) };
      if (path.endsWith("/revisions/3/restore")) return restore();
      throw new Error(`unexpected ${path}`);
    });
  }

  it("restores with compare-and-swap on the current revision and adopts the result", async () => {
    mockHistory(() => ({ ...design, revision: 7 }));
    const prepare = vi.fn(async () => 5);
    const onRestored = vi.fn();
    wrap(<HistoryPanel designId={1} canEdit values={{ name: "Priya" }} prepare={prepare} onRestored={onRestored} onReload={vi.fn()} />);
    const row = await screen.findByRole("button", { name: /version 3/i });
    expect(within(row).getByText("Published")).toBeInTheDocument();
    expect(within(screen.getByRole("button", { name: /version 5/i })).getByText("Current")).toBeInTheDocument();
    fireEvent.click(row);
    expect(await screen.findByRole("img", { name: "Version 3, front" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restore this version" }));
    fireEvent.click(await screen.findByRole("button", { name: "Restore as a draft" }));
    await waitFor(() => expect(onRestored).toHaveBeenCalledWith(expect.objectContaining({ revision: 7 })));
    const call = api.staffRequest.mock.calls.find((item) => String(item[0]).endsWith("/restore"))!;
    expect(body(call)).toEqual({ revision: 5 });
    expect(prepare).toHaveBeenCalled();
    expect(await screen.findByText(/version 3 is now your draft/i)).toBeInTheDocument();
  });

  it("shows the conflict message and offers to load the other version on 409", async () => {
    mockHistory(() => { throw new StructuredApiError(409, { detail: "Changed" }); });
    const onReload = vi.fn();
    wrap(<HistoryPanel designId={1} canEdit values={{ name: "Priya" }} prepare={async () => 5} onRestored={vi.fn()} onReload={onReload} />);
    fireEvent.click(await screen.findByRole("button", { name: /version 3/i }));
    await screen.findByRole("img", { name: "Version 3, front" });
    fireEvent.click(screen.getByRole("button", { name: "Restore this version" }));
    fireEvent.click(await screen.findByRole("button", { name: "Restore as a draft" }));
    expect(await screen.findByText(/someone else saved this design/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Load their version" }));
    expect(onReload).toHaveBeenCalled();
  });

  it("hides restore for people who cannot edit", async () => {
    mockHistory(() => design);
    wrap(<HistoryPanel designId={1} canEdit={false} values={{}} prepare={async () => 5} onRestored={vi.fn()} onReload={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /version 3/i }));
    await screen.findByRole("img", { name: "Version 3, front" });
    expect(screen.queryByRole("button", { name: "Restore this version" })).toBeNull();
  });
});

describe("sheet preview", () => {
  it("previews with the chosen paper and queues the print job with the same settings", async () => {
    api.staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/preview")) {
        const sent = JSON.parse(String(init?.body));
        return { total: 23, per_page: 10, sheets: 3, paper: sent.paper, order: sent.order, front: "data:image/png;base64,AA",
          back: "data:image/png;base64,AA", mixed_sizes: true };
      }
      if (path === "/jobs") return { id: 9 };
      throw new Error(`unexpected ${path}`);
    });
    const onClose = vi.fn();
    wrap(<SheetPreviewDialog open onClose={onClose} previewPath="/jobs/preview" jobsPath="/jobs" filter={{ status: "active", card_ids: [4, 5] }} />);
    expect(await screen.findByText(/23 cards on 3 sheets \(\+ 3 backs\)/)).toBeInTheDocument();
    expect(screen.getByText(/different card size/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /first A4 sheet of card fronts/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Letter" }));
    await screen.findByRole("img", { name: /first Letter sheet/ });
    const previews = api.staffRequest.mock.calls.filter((call) => String(call[0]).endsWith("/preview"));
    expect(body(previews[previews.length - 1])).toEqual({ status: "active", card_ids: [4, 5], paper: "letter", order: "duplex", crop_marks: true });
    fireEvent.click(screen.getByRole("button", { name: "Start print job" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const job = api.staffRequest.mock.calls.find((call) => call[0] === "/jobs")!;
    expect(body(job)).toEqual({ kind: "bulk_sheet", status: "active", card_ids: [4, 5], paper: "letter", order: "duplex", crop_marks: true });
  });

  it("shows an error with a retry", async () => {
    api.staffRequest.mockRejectedValue(new Error("Too many previews"));
    wrap(<SheetPreviewDialog open onClose={vi.fn()} previewPath="/jobs/preview" jobsPath="/jobs" filter={{}} />);
    expect(await screen.findByText(/couldn.t load sheet preview/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start print job" })).toBeDisabled();
  });
});
