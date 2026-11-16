import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StructuredApiError, staffRequest } from "../../lib/api";
import { reportItem } from "../../test/analyticsFixtures";
import { CashInHand } from "./CashInHand";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: vi.fn() }));

it.each([[403, 503], [503, 403], [503, 503]] as const)(
  "retries each failed cash read independently (catalogue %s, report %s) and conceals retained money", async (catalogStatus, reportStatus) => {
    let failed = false;
    const attempts = { catalog: 0, report: 0 };
    const catalog = { results: [reportItem("cash-in-hand", { chart_spec: null, grains: ["day"] })] };
    const report = { typed_rows: [{ collector_id: 4, collector: "Private collector", currency: "inr", cash_in_hand: "1000.00" }], rows: [] };
    const code = (status: number) => status === 403 ? "permission_denied" : "service_unavailable";
    vi.mocked(staffRequest).mockImplementation(async path => {
      const kind = path.endsWith("/reports/catalog") ? "catalog" : "report";
      attempts[kind]++;
      if (failed) {
        const status = kind === "catalog" ? catalogStatus : reportStatus;
        throw new StructuredApiError(status, { code: code(status), detail: `${kind} ${code(status)}` });
      }
      return kind === "catalog" ? catalog : report;
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><CashInHand makerspaceId={3} canHandover /></QueryClientProvider>);
    await screen.findByText("Private collector");
    fireEvent.click(screen.getByRole("button", { name: "Record hand-over" }));
    await screen.findByRole("dialog");
    failed = true;
    await act(async () => { await client.refetchQueries(); });
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
    const states = client.getQueryCache().getAll().filter(query => ["report-catalog", "operations-report"].includes(String(query.queryKey[0])));
    expect(states).toHaveLength(2);
    for (const query of states) {
      const status = query.queryKey[0] === "report-catalog" ? catalogStatus : reportStatus;
      expect([query.state.status, (query.state.error as StructuredApiError).status, (query.state.error as StructuredApiError).code])
        .toEqual(["error", status, code(status)]);
      expect(query.state.data).toBeDefined();
    }
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText("Private collector")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: "Record hand-over" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(Number(catalogStatus === 503) + Number(reportStatus === 503));
    expect(attempts).toEqual({ catalog: 2, report: 2 });
    failed = false;
    for (const button of screen.getAllByRole("button", { name: "Retry" })) fireEvent.click(button);
    await waitFor(() => expect(attempts).toEqual({ catalog: catalogStatus === 503 ? 3 : 2, report: reportStatus === 503 ? 3 : 2 }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Retry" })).toBeNull());
    if (catalogStatus === 503 && reportStatus === 503) expect(await screen.findByText("Private collector")).toBeVisible();
    else expect(screen.queryByRole("table")).toBeNull();
  },
);
