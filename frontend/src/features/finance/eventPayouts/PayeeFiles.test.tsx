import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import { PayeeFilesSection } from "./PayeeFiles";
import { payout } from "./testData";
import type { PayoutDetail } from "./types";

vi.mock("../../../lib/api", () => ({ memberRequest: vi.fn(), staffRequest: vi.fn() }));
const payee = { id: "payee-1", version: 2, state: "current", country: "IN", method: "bank_transfer", masked_details: "••7890", verified: false };
const row: PayoutDetail = { ...payout, payee, allowed_actions: ["view", "submit_payee"] };
const context = { payee, allowed_actions: ["submit_payee"], templates: [], routing_document_methods: [["IN", "bank_transfer"]],
  disclosure_version: 1, disclosure: "" };
const base = "/member/event-payouts/obligation/payee-files/";
const fetchMock = vi.fn();
let version = 3;
let assetVersion = 1;
let listed: Array<Record<string, unknown>> = [];

function mount(data: PayoutDetail = row) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <PayeeFilesSection actorId={73} payout={data} /></QueryClientProvider>);
}
beforeEach(() => {
  version = 3; assetVersion = 1; listed = [];
  fetchMock.mockReset().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(memberRequest).mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === "/member/event-payouts/obligation/payee/") return context;
    if (path === "/member/event-payouts/obligation/") return { ...row, version };
    if (path === base && !init?.method) return listed;
    if (path === base && init?.method === "POST") {
      version += 1;
      return { asset_id: 8, generation: 1, state: "initiated", upload: { method: "POST", url: "https://s3.test/bucket", fields: { key: "staging/8" }, expires_at: "" } };
    }
    if (path === `${base}8/` && !init?.method) return { asset_id: 8, generation: 1, version: assetVersion, state: assetVersion > 1 ? "ready" : "uploaded",
      filename: "bank.pdf", bytes: 3, scan_status: "clean", error_code: "" };
    if (path === `${base}8/complete/`) { version += 1; assetVersion += 1; return { state: "ready" }; }
    if (path === `${base}8/` && init?.method === "DELETE") { version += 1; return { state: "expired" }; }
    throw new Error(`Unexpected ${path}`);
  });
});
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });

const bodyOf = (path: string, method: string) => JSON.parse(String(vi.mocked(memberRequest).mock.calls
  .find(([p, init]) => p === path && init?.method === method)![1]!.body));

it("uploads a routing document to the presigned form and completes it against current versions", async () => {
  mount();
  const file = new File(["pdf"], "bank.pdf", { type: "application/pdf" });
  fireEvent.change(await screen.findByLabelText("Upload a routing document"), { target: { files: [file] } });
  expect(await screen.findByText("bank.pdf · Ready for finance review")).toBeInTheDocument();
  expect(bodyOf(base, "POST")).toMatchObject({ expected_version: 3, payee_revision_id: "payee-1", expected_payee_version: 2,
    question_id: "routing_document", filename: "bank.pdf", bytes: 3, mime: "application/pdf" });
  const form = fetchMock.mock.calls[0][1].body as FormData;
  expect(fetchMock.mock.calls[0][0]).toBe("https://s3.test/bucket");
  expect(form.get("key")).toBe("staging/8");
  expect(bodyOf(`${base}8/complete/`, "POST")).toMatchObject({ expected_version: 4, expected_asset_version: 1, generation: 1 });
  fireEvent.click(screen.getByRole("button", { name: "Remove bank.pdf" }));
  await waitFor(() => expect(screen.queryByText(/bank\.pdf/)).toBeNull());
  expect(bodyOf(`${base}8/`, "DELETE")).toMatchObject({ expected_version: 5, expected_asset_version: 2, generation: 1 });
});

it("stays hidden once routing is verified, and never asks for context without the owner's submit action", () => {
  mount({ ...row, payee: { ...payee, verified: true } });
  mount({ ...row, allowed_actions: ["view"] });
  expect(screen.queryByLabelText("Upload a routing document")).toBeNull();
  expect(memberRequest).not.toHaveBeenCalled();
});

it("refuses an unsupported file type before contacting the server", async () => {
  mount();
  fireEvent.change(await screen.findByLabelText("Upload a routing document"), { target: { files: [new File(["x"], "a.txt", { type: "text/plain" })] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("Choose a PDF, JPEG or PNG up to 10 MB.");
  expect(vi.mocked(memberRequest).mock.calls.some(([path, init]) => path === base && init?.method === "POST")).toBe(false);
});

it("loads the owner's already-uploaded files on mount, metadata only", async () => {
  listed = [{ id: 5, filename: "earlier letter.pdf", size: 2048, uploaded_at: "2026-11-01T10:00:00Z", status: "ready" }];
  mount();
  expect(await screen.findByText("earlier letter.pdf · Ready for finance review")).toBeInTheDocument();
  expect(vi.mocked(memberRequest)).toHaveBeenCalledWith(base, { cache: "no-store" });
  expect(screen.getByRole("button", { name: "Remove earlier letter.pdf" })).toBeInTheDocument();
});

it("says so when the existing files cannot be loaded", async () => {
  const original = vi.mocked(memberRequest).getMockImplementation()!;
  vi.mocked(memberRequest).mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === base && !init?.method) throw new Error("offline");
    return original(path, init);
  });
  mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("Your uploaded files could not be loaded.");
});
