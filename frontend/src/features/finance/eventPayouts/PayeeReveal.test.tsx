import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PayeeReveal } from "./PayeeReveal";
import { memberRequest, staffRequest } from "../../../lib/api";
import { scope } from "./testData";
vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn(), memberRequest: vi.fn() }));
afterEach(() => { vi.clearAllMocks(); vi.useRealTimers(); });
const open = () => {
  fireEvent.change(screen.getByLabelText("Inspection reason code"), { target: { value: "routing_review" } });
  fireEvent.click(screen.getByRole("button", { name: "Reveal for inspection" }));
};
describe("audited payee inspection", () => {
  it("uses no-store audited POST and clears plaintext on blur", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ details: { account_number: "001234567890" } });
    const storage = vi.spyOn(Storage.prototype, "setItem");
    render(<PayeeReveal scope={scope} obligationId="safe-id" version={3} allowed />);
    open(); await screen.findByText("001234567890");
    expect(storage).not.toHaveBeenCalled();
    const [path, options] = vi.mocked(staffRequest).mock.calls[0];
    expect(path).toBe("/admin/makerspaces/2/event-payouts/safe-id/payee/reveal/");
    expect(options).toMatchObject({ cache: "no-store", method: "POST" });
    expect(JSON.parse(options!.body as string)).toMatchObject({ expected_version: 3, reason_code: "routing_review", purpose: "verify_routing",
      operation_id: (options!.headers as Record<string, string>)["Idempotency-Key"] });
    fireEvent.blur(window); expect(screen.queryByText("001234567890")).toBeNull();
    storage.mockRestore();
  });
  it("does not release an in-flight response after focus or permission loss", async () => {
    let resolve!: (value: unknown) => void;
    vi.mocked(staffRequest).mockReturnValue(new Promise(value => { resolve = value; }));
    const view = render(<PayeeReveal scope={scope} obligationId="safe-id" version={3} allowed />);
    open(); fireEvent.blur(window);
    await act(async () => resolve({ details: { account_number: "001234567890" } }));
    expect(screen.queryByText("001234567890")).toBeNull();
    view.rerender(<PayeeReveal scope={scope} obligationId="safe-id" version={3} allowed={false} />);
    expect(screen.queryByRole("button", { name: "Reveal for inspection" })).toBeNull();
  });
  it("clears after 30 seconds and uses member auth for owner inspection", async () => {
    vi.useFakeTimers();
    vi.mocked(memberRequest).mockResolvedValue({ details: { holder_name: "Private owner" } });
    render(<PayeeReveal actorId={73} obligationId="safe-id" version={3} allowed />);
    open(); await act(async () => {});
    expect(screen.getByText("Private owner")).toBeVisible();
    expect(memberRequest).toHaveBeenCalledWith("/member/event-payouts/safe-id/payee/reveal/", expect.anything());
    act(() => vi.advanceTimersByTime(30_000));
    expect(screen.queryByText("Private owner")).toBeNull();
  });
  it("never shows another actor's response on a scope change", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ details: { holder_name: "Private actor" } });
    const view = render(<PayeeReveal scope={scope} obligationId="safe-id" version={3} allowed />);
    open(); await screen.findByText("Private actor");
    view.rerender(<PayeeReveal scope={{ ...scope, actorId: 99 }} obligationId="safe-id" version={3} allowed />);
    await waitFor(() => expect(screen.queryByText("Private actor")).toBeNull());
  });
});
