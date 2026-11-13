import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StepDocuments } from "./StepDocuments";
import { baseSpec, context, renderWithQuery } from "./test/stepTestKit";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async importOriginal => ({ ...(await importOriginal<object>()), staffRequest }));

const setup = { booking_slot_minutes: null, booking_buffer_before_minutes: null, booking_buffer_after_minutes: null, booking_approval_mode: "", training_notes: "", notes_at_session_start: false, notes_at_job_request: false, updated_at: null };
const doc = { id: 3, title: "Manual", original_filename: "manual.pdf", content_type: "application/pdf", size_bytes: 2048, member_visible: true, created_at: "2026-11-01T00:00:00Z" };
const order: string[] = [];
const calls = (method: string, suffix: string) => staffRequest.mock.calls.filter(([path, init]) => (init?.method ?? "GET") === method && String(path).endsWith(suffix));

describe("StepDocuments", () => {
  beforeEach(() => {
    order.length = 0; staffRequest.mockReset();
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => { order.push(`${init.method} ${url}`); return new Response(null, { status: 200 }); }));
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (path.endsWith("/setup")) return setup;
      if (path.endsWith("/documents/presign")) { order.push("presign"); return { object_key: "type-docs/1/9/abc.pdf", upload: { url: "https://storage.test/put", method: "PUT", headers: { "Content-Type": "application/pdf" } } }; }
      if (path.endsWith("/documents") && method === "POST") { order.push("attach"); return doc; }
      if (path.endsWith("/documents")) return [doc];
      if (path.endsWith("/documents/3") && method === "DELETE") return null;
      if (path.endsWith("/documents/3")) return { url: "https://signed.test/manual" };
      return {};
    });
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("uploads through presign, then storage, then attach, with the member-visible choice", async () => {
    renderWithQuery(<StepDocuments ctx={context()} />);
    await screen.findByText("Manual");
    const file = new File(["%PDF"], "guide.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("File"), { target: { files: [file] } });
    fireEvent.click(screen.getByLabelText("Members can open this before they use the machine"));
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await waitFor(() => expect(order).toEqual(["presign", "PUT https://storage.test/put", "attach"]));
    expect(JSON.parse(calls("POST", "/documents/presign")[0][1].body)).toEqual({ filename: "guide.pdf", content_type: "application/pdf" });
    expect(JSON.parse(calls("POST", "/documents")[0][1].body)).toEqual({ object_key: "type-docs/1/9/abc.pdf", title: "guide.pdf", original_filename: "guide.pdf", member_visible: false });
  });

  it("shows a storage or limit refusal from the attach step", async () => {
    const base = staffRequest.getMockImplementation()!;
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/documents") && init?.method === "POST") throw new Error("This space has no storage left.");
      return base(path, init);
    });
    renderWithQuery(<StepDocuments ctx={context()} />);
    await screen.findByText("Manual");
    fireEvent.change(screen.getByLabelText("File"), { target: { files: [new File(["x"], "big.pdf", { type: "application/pdf" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText("This space has no storage left.")).toBeVisible();
  });

  it("deletes a document after confirming", async () => {
    renderWithQuery(<StepDocuments ctx={context()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete Manual" }));
    expect(calls("DELETE", "/documents/3")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(calls("DELETE", "/documents/3")).toHaveLength(1));
  });

  it("saves the training notes and the two show-where toggles, starting from the template's note", async () => {
    renderWithQuery(<StepDocuments ctx={context({ spec: baseSpec as never })} />);
    const notes = await screen.findByLabelText(/Training notes/);
    expect(notes).toHaveValue("Wear eye protection.");
    fireEvent.click(screen.getByLabelText("Show the notes when a member starts a session"));
    fireEvent.click(screen.getByRole("button", { name: "Save training notes" }));
    await waitFor(() => expect(calls("PATCH", "/setup")).toHaveLength(1));
    expect(JSON.parse(calls("PATCH", "/setup")[0][1].body)).toEqual({ training_notes: "Wear eye protection.", notes_at_session_start: true, notes_at_job_request: false });
  });
});
