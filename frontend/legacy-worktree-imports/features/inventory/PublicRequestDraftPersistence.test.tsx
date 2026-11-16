// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: PublicRequestPanel.requestAccess is now only "contact" and PricePreview requires TenantProvider; harness not updated.
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
/**
 * On phones the request panel lives in a sheet that unmounts its content when closed. The draft, the
 * contact fields and the account-less reference token are owned by the page's `useRequestDraft`, so a
 * close/reopen (an unmount/remount of the panel) must not lose any of them.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { submitPublicRequest, getAccessToken, refreshAccessToken } = vi.hoisted(() => ({
  submitPublicRequest: vi.fn(),
  getAccessToken: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return { ...actual, submitPublicRequest };
});
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, getAccessToken, refreshAccessToken };
});

import { PublicRequestPanel } from "./PublicRequestPanel";
import { useRequestDraft } from "./useRequestDraft";

const ITEMS = [{ productId: 7, name: "Logic analyzer", quantity: 1 }];

// Stands in for the page: owns the draft above a panel that is mounted/unmounted like the phone sheet.
function Harness() {
  const [open, setOpen] = useState(true);
  const draft = useRequestDraft();
  return (
    <>
      <button type="button" onClick={() => setOpen(value => !value)}>toggle sheet</button>
      {open ? (
        <PublicRequestPanel requestAccess="anyone" items={ITEMS} makerspaceSlug="makerspace" onClear={() => {}} draft={draft} />
      ) : <p>sheet closed</p>}
    </>
  );
}

describe("request draft survives the sheet unmounting", () => {
  beforeEach(() => {
    submitPublicRequest.mockReset();
    submitPublicRequest.mockResolvedValue({ public_token: "tok-keep-1" });
    getAccessToken.mockReset();
    getAccessToken.mockReturnValue("");
    refreshAccessToken.mockReset();
    refreshAccessToken.mockResolvedValue(false);
  });

  function renderHarness() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    return render(<QueryClientProvider client={queryClient}><Harness /></QueryClientProvider>);
  }

  it("keeps the purpose and contact fields across close and reopen", async () => {
    renderHarness();
    await waitFor(() => expect(screen.getByLabelText(/your name/i)).toBeTruthy());
    fireEvent.change(screen.getByLabelText(/your name/i), { target: { value: "Ada Lovelace" } });
    fireEvent.change(screen.getByLabelText(/request purpose/i), { target: { value: "Bench diagnostics" } });

    fireEvent.click(screen.getByRole("button", { name: /toggle sheet/i }));
    expect(screen.getByText("sheet closed")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /toggle sheet/i }));

    await waitFor(() => expect(screen.getByLabelText(/your name/i)).toBeTruthy());
    expect((screen.getByLabelText(/your name/i) as HTMLInputElement).value).toBe("Ada Lovelace");
    expect((screen.getByLabelText(/request purpose/i) as HTMLInputElement).value).toBe("Bench diagnostics");
  });

  it("keeps the account-less reference token across close and reopen", async () => {
    renderHarness();
    await waitFor(() => expect(screen.getByLabelText(/your name/i)).toBeTruthy());
    fireEvent.change(screen.getByLabelText(/your name/i), { target: { value: "Ada Lovelace" } });
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: "ada@example.test" } });
    fireEvent.change(screen.getByLabelText(/request purpose/i), { target: { value: "Bench diagnostics" } });
    fireEvent.click(screen.getByRole("button", { name: /submit request/i }));
    await waitFor(() => expect(screen.getByText("tok-keep-1")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /toggle sheet/i }));
    fireEvent.click(screen.getByRole("button", { name: /toggle sheet/i }));

    await waitFor(() => expect(screen.getByText("tok-keep-1")).toBeTruthy());
  });
});
