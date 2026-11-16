import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { UnitPicker } from "./UnitPicker";
import type { MemberUnit } from "./unitsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const unit = (id: number, parent: number | null, name: string, path: string, level: number, archived = false): MemberUnit => ({
  id, parent_id: parent, name, slug: name, code: name.toUpperCase().slice(0, 6), level, level_name: "", path, sort_order: 0,
  archived, has_payment_instructions: false,
});
const renderPicker = (onChange = vi.fn(), value: number | null = null) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <UnitPicker makerspaceId={3} value={value} onChange={onChange} noneLabel="No unit" /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("UnitPicker", () => {
  it("offers only the units the server returns for this caller, indented, without archived ones", async () => {
    // A unit-scoped lead: the server sends their subtree only (Kochi and below), parent out of view.
    staffRequest.mockResolvedValue({ levels: [], templates: [], limit: null, used: 2, scoped: true,
      units: [unit(2, 1, "Kochi", "/N/KOCHI/", 1), unit(5, 2, "Fort", "/N/KOCHI/FORT/", 2), unit(6, 2, "Old", "/N/KOCHI/OLD/", 2, true)] });
    const onChange = vi.fn();
    renderPicker(onChange);
    const select = await screen.findByRole("combobox", { name: "Unit" });
    await waitFor(() => expect(within(select).getAllByRole("option").map(option => option.textContent)).toEqual(
      ["No unit", "Kochi · KOCHI", " Fort · FORT"]));
    fireEvent.change(select, { target: { value: "5" } });
    expect(onChange).toHaveBeenCalledWith(5);
    fireEvent.change(select, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("keeps an archived current value readable but not choosable again", async () => {
    staffRequest.mockResolvedValue({ levels: [], templates: [], limit: null, used: 0, scoped: false,
      units: [unit(6, null, "Old", "/OLD/", 0, true)] });
    renderPicker(vi.fn(), 6);
    expect(await screen.findByRole("option", { name: "Old · OLD (archived)" })).toBeDisabled();
  });

  it("renders nothing while member units are off", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(404, { code: "feature_disabled", detail: "off" })));
    const { container } = renderPicker();
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
