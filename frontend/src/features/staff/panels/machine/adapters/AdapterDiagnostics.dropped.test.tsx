import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdapterDiagnostics } from "./AdapterDiagnostics";
import type { AdapterSummary } from "./adaptersApi";

vi.mock("../../../../../lib/api", () => ({ staffRequest: vi.fn().mockResolvedValue({ results: [] }) }));

const base = { online: true, offline_since: null, id: "a1", name: "Bridge", status: "active", last_seen_at: null, adapter_kind: "x", vendor: "", software_version: "",
  capabilities: [], config_version: 1, hello_at: null, bindings: [] } as unknown as AdapterSummary;
const show = (adapter: AdapterSummary) => render(<QueryClientProvider client={new QueryClient()}>
  <AdapterDiagnostics makerspaceId={7} adapter={adapter} bundles={false} /></QueryClientProvider>);

describe("adapter diagnostics: dropped telemetry (decision 328a)", () => {
  it("says how many samples were dropped because the limit was reached", () => {
    show({ ...base, telemetry_dropped_7d: 1234 });
    expect(screen.getByText(/1,234 telemetry samples dropped: limit reached/)).toBeInTheDocument();
  });
  it("shows nothing when none were dropped", () => {
    show(base);
    expect(screen.queryByText(/telemetry samples dropped/)).not.toBeInTheDocument();
  });
});
