import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { memberRequest } from "../../lib/api";
import { prefillDetails, saveIntentStatus } from "./api";
import { FormSaveIntentsNotice, SaveDetailChoice, useRegistrationSavedDetails } from "./RegistrationSavedDetails";
import { parseFormSaveIntents, parseIntent, parsePrefill } from "./parsers";
import type { FormSaveIntent, Prefill, PrefillSelector } from "./types";

vi.mock("./api", () => ({ prefillDetails: vi.fn(), saveIntentStatus: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: vi.fn(), memberRequestBlob: vi.fn() }));
const op = (id: number) => `00000000-0000-4000-8000-${String(id).padStart(12, "0")}`;
const empty: Prefill = { form_revision: 3, event_date_revision: 7, values: {}, saved_detail_versions: {}, save_defaults: {}, derivation_inputs: {} };
const clients: QueryClient[] = [];
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  return { client, Wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> };
}
function requested(slot: "base" | `stage:${number}`, id: number, state: "pending" | "applied" | "conflict" | "failed" = "pending"): FormSaveIntent {
  return { slot, operation_id: op(id), intent_id: op(id + 100), state, fields: {}, status_url: `/api/v1/member/saved-details/save-intents/${op(id)}/` };
}
const notRequested: FormSaveIntent = { slot: "stage:9", operation_id: op(3), intent_id: null, state: "not_requested", fields: {}, status_url: null };
beforeEach(() => { vi.resetAllMocks(); vi.mocked(prefillDetails).mockResolvedValue(empty); });
afterEach(() => { clients.forEach(client => client.clear()); clients.length = 0; document.documentElement.classList.remove("dark"); });

describe("inline form intent projections", () => {
  it("accepts base plus stages, including unchanged field results and no-save forms", () => {
    const items = [requested("base", 1, "applied"), { ...requested("stage:8", 2, "applied"), fields: { institution: { state: "unchanged", version: 1 } } }, notRequested];
    expect(parseFormSaveIntents(items)).toEqual(items);
    expect(parseIntent({ operation_id: op(2), state: "applied", fields: items[1].fields, retryable: false }).fields.institution?.state).toBe("unchanged");
  });

  it.each([
    [requested("base", 1), requested("stage:8", 1)],
    [requested("base", 1), requested("base", 2)],
    [{ ...requested("stage:8", 1), slot: "stage:0" }],
    [{ ...requested("stage:8", 1), status_url: "https://outside.test/private" }],
    [{ ...notRequested, intent_id: op(9) }],
    [{ ...requested("stage:8", 1), fields: { bank_account: { state: "applied" } } }],
  ])("rejects ambiguous or unsafe per-form status data %#", (...items) => {
    expect(() => parseFormSaveIntents(items)).toThrow();
  });

  it("rejects DOB, age metadata or derivations from a stage prefill response", () => {
    expect(parsePrefill(empty, true)).toEqual(empty);
    for (const name of ["values", "saved_detail_versions", "save_defaults"])
      expect(() => parsePrefill({ ...empty, [name]: { date_of_birth: name === "values" ? "2004-05-12" : name === "save_defaults" ? false : 1 } }, true)).toThrow();
    expect(() => parsePrefill({ ...empty, derivation_inputs: { age: { source: { kind: "saved_detail", field_key: "date_of_birth", version: 1 }, value: 22, as_of_date: "2026-12-01" } } }, true)).toThrow();
  });
});

describe("per-form status UI", () => {
  it.each([false, true])("shows each form separately using inherited theme tokens (dark=%s)", async dark => {
    document.documentElement.classList.toggle("dark", dark);
    const { Wrapper } = wrapper();
    const items = [requested("base", 1, "applied"), requested("stage:8", 2, "conflict"), notRequested];
    const { container } = render(<FormSaveIntentsNotice actorId={7} intents={items}
      formLabels={{ base: "Application", "stage:8": "Travel preferences", "stage:9": "Arrival plans" }} />, { wrapper: Wrapper });
    const region = screen.getByRole("region", { name: "Saved details updates" });
    expect(within(region).getByText("Application")).toBeVisible();
    expect(within(region).getByText("Your chosen details were saved privately.")).toBeVisible();
    expect(within(region).getByRole("link", { name: "Review saved details" })).toHaveAttribute("href", "/member/account/saved-details");
    expect(within(region).getByText("No details selected for saving.")).toBeVisible();
    expect(saveIntentStatus).not.toHaveBeenCalled();
    expect(container.querySelector(".bg-panel.text-ink")).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("polls the child operation only and refreshes the account list when applied", async () => {
    const { client, Wrapper } = wrapper();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    vi.mocked(saveIntentStatus).mockResolvedValueOnce({ operation_id: op(2), state: "pending", fields: {}, retryable: true })
      .mockResolvedValue({ operation_id: op(2), state: "applied", fields: { institution: { state: "unchanged", version: 1 } }, retryable: false });
    render(<FormSaveIntentsNotice actorId={7} intents={[requested("stage:8", 2), notRequested]} />, { wrapper: Wrapper });
    await waitFor(() => expect(saveIntentStatus).toHaveBeenCalledWith(op(2)));
    await waitFor(() => expect(screen.getByText("Your chosen details were saved privately.")).toBeVisible(), { timeout: 4500 });
    expect(saveIntentStatus).not.toHaveBeenCalledWith(op(3));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["member", "saved-details", window.location.host, 7], exact: true });
  }, 10000);

  it("keeps submission success explicit when a status request fails", async () => {
    const { Wrapper } = wrapper();
    vi.mocked(saveIntentStatus).mockRejectedValue(new Error("Unavailable"));
    render(<FormSaveIntentsNotice actorId={7} intents={[requested("stage:8", 2)]} />, { wrapper: Wrapper });
    expect(await screen.findByText("Your event submission succeeded. Saved details status is temporarily unavailable.")).toBeVisible();
  });

  it("keeps sensitive save consent unchecked until the member chooses", () => {
    const onChange = vi.fn();
    render(<SaveDetailChoice fieldKey="dietary_needs" sensitive checked={false} onChange={onChange} />);
    const choice = screen.getByRole("checkbox", { name: /Save to my private details.*sensitive.*dietary needs/ });
    expect(choice).not.toBeChecked();
    fireEvent.click(choice);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

describe("stage prefill query isolation", () => {
  const selector = (id: number, stage = 8): PrefillSelector => ({ context: { event_id: 42, makerspace_id: 9, subject_kind: "stage_response",
    stage_form_id: stage, creation_operation_id: op(id) }, form_id: "arrival", form_revision: 3, event_date_revision: 7 });

  it("posts the typed virtual selector and rejects a stage response containing a DOB source", async () => {
    const api = await vi.importActual<typeof import("./api")>("./api");
    vi.mocked(memberRequest).mockResolvedValueOnce(empty);
    await expect(api.prefillDetails(selector(1))).resolves.toEqual(empty);
    expect(memberRequest).toHaveBeenCalledWith("/member/saved-details/prefill/", { method: "POST", body: JSON.stringify(selector(1)) });
    vi.mocked(memberRequest).mockResolvedValueOnce({ ...empty, values: { date_of_birth: "2004-05-12" } });
    await expect(api.prefillDetails(selector(1))).rejects.toThrow();
  });

  it("separates virtual subjects and stages, and does not evict a sibling form on unmount", async () => {
    const { client, Wrapper } = wrapper();
    const first = renderHook(() => useRegistrationSavedDetails(7, selector(1)), { wrapper: Wrapper });
    const second = renderHook(() => useRegistrationSavedDetails(7, selector(2)), { wrapper: Wrapper });
    const third = renderHook(() => useRegistrationSavedDetails(7, selector(2, 9)), { wrapper: Wrapper });
    await waitFor(() => expect(first.result.current.isSuccess && second.result.current.isSuccess && third.result.current.isSuccess).toBe(true));
    expect(prefillDetails).toHaveBeenCalledTimes(3);
    expect(client.getQueryCache().findAll()).toHaveLength(3);
    first.unmount();
    await waitFor(() => expect(client.getQueryCache().findAll()).toHaveLength(2));
    expect(second.result.current.data).toEqual(empty);
    second.unmount(); third.unmount();
    await waitFor(() => expect(client.getQueryCache().findAll()).toHaveLength(0));
  });

  it("reloads for a new event date without converting the stage to an age review", async () => {
    const { Wrapper } = wrapper();
    const { result, rerender } = renderHook(({ revision }) => useRegistrationSavedDetails(7, { ...selector(1), event_date_revision: revision }),
      { wrapper: Wrapper, initialProps: { revision: 7 } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    rerender({ revision: 8 });
    await waitFor(() => expect(prefillDetails).toHaveBeenCalledWith({ ...selector(1), event_date_revision: 8 }));
    expect(result.current.data?.derivation_inputs || {}).toEqual({});
  });
});
