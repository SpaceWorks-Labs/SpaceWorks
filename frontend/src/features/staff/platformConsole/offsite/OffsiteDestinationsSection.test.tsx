import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../../lib/api";
import { OffsiteDestinationsSection } from "./OffsiteDestinationsSection";

vi.mock("../../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const destination = { id: 3, name: "r2-offsite", kind: "s3", endpoint_url: "https://r2.example.com", bucket: "spaceworks", region: "",
  prefix: "nightly", addressing_style: "auto", credentials_set: true, enabled: true, retention_days: 90, created_at: "2026-11-01T00:00:00Z",
  updated_at: "2026-11-01T00:00:00Z", retired_at: null, last_success_at: "2026-11-08T03:00:00Z", last_error_code: "" };
const upload = { id: 9, destination: "r2-offsite", archive_id_snapshot: "0b7c9f3e-0000-4000-8000-000000000001", scope_snapshot: "makerspace",
  makerspace_id_snapshot: 7, archive_completed_at_snapshot: "2026-11-08T02:00:00Z", expected_size_bytes: 1024, state: "bytes_verified",
  attempts: 1, uploaded_at: "2026-11-08T03:00:00Z", verified_at: "2026-11-08T03:05:00Z", expires_at: "2027-02-06T03:00:00Z", deleted_at: null, last_error_code: "" };

const calls = (method: string) => request.mock.calls.filter(([, init]) => init?.method === method);

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><OffsiteDestinationsSection /></QueryClientProvider>);
}

describe("OffsiteDestinationsSection", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (path, init) => {
      if (path.endsWith("/test")) return { ok: true, error_code: "" } as never;
      if (init?.method) return { ...destination, detail: "ok" } as never;
      if (path.includes("/uploads")) return page([upload]) as never;
      return page([destination]) as never;
    });
  });

  it("lists each destination with where it pushes and its state", async () => {
    renderSection();
    expect((await screen.findAllByText("r2-offsite")).length).toBeGreaterThan(0);
    expect(screen.getByText(/spaceworks\/nightly/)).toBeInTheDocument();
    expect(screen.getByText("Pushing")).toBeInTheDocument();
  });

  it("tests a destination and starts a push on the platform session", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: "Test" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/backup-destinations/3/test", expect.objectContaining({ method: "POST" }), "platform"));
    fireEvent.click(screen.getByRole("button", { name: "Push now" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/backup-destinations/push", expect.objectContaining({ method: "POST" }), "platform"));
  });

  it("asks for the destination name before retiring it", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: /^Retire…s*r2-offsite$/ }));
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Retire destination" });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Type r2-offsite to confirm"), { target: { value: "r2-offsite" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/backup-destinations/3/retire", expect.objectContaining({ method: "POST" }), "platform"));
  });

  it("requires both keys for a new destination and never sends blank ones on an edit", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: /New destination/ }));
    const form = screen.getByRole("form", { name: "New offsite destination" });
    fireEvent.change(within(form).getByLabelText("Name"), { target: { value: "b2" } });
    fireEvent.change(within(form).getByLabelText("Bucket"), { target: { value: "copies" } });
    fireEvent.change(within(form).getByLabelText("Access key ID"), { target: { value: "AKIA" } });
    expect(within(form).getByRole("button", { name: "Add destination" })).toBeDisabled();
    fireEvent.change(within(form).getByLabelText("Secret access key"), { target: { value: "secret" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add destination" }));
    await waitFor(() => expect(calls("POST").some(([path]) => path === "/admin/platform/backup-destinations")).toBe(true));
    const body = JSON.parse(String(calls("POST").find(([path]) => path === "/admin/platform/backup-destinations")![1]!.body));
    expect(body).toMatchObject({ name: "b2", bucket: "copies", access_key_id: "AKIA", secret_access_key: "secret", retention_days: 90 });

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const edit = screen.getByRole("form", { name: "Edit r2-offsite" });
    fireEvent.click(within(edit).getByRole("button", { name: "Save destination" }));
    await waitFor(() => expect(calls("PATCH").length).toBe(1));
    const patchBody = JSON.parse(String(calls("PATCH")[0][1]!.body));
    expect(patchBody).not.toHaveProperty("access_key_id");
    expect(patchBody).not.toHaveProperty("secret_access_key");
  });

  it("offers restoring the primary copy from a verified offsite copy", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: "Copies" }));
    expect(await screen.findByText("Verified copy")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restore primary…" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Restore primary copy" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(`/admin/platform/backups/${upload.archive_id_snapshot}/rehydrate`,
      expect.objectContaining({ method: "POST", body: JSON.stringify({ destination: 3 }) }), "platform"));
  });
});
