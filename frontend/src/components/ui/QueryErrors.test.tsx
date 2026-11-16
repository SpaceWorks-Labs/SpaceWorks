import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { QueryErrors } from "./QueryErrors";
import { ErrorBlock } from "./ErrorBlock";

it("gives each independently failed query a retry that attempts that query again", async () => {
  const first = vi.fn().mockRejectedValue(new StructuredApiError(503, { code: "service_unavailable", detail: "First unavailable" }));
  const second = vi.fn().mockRejectedValue(new StructuredApiError(503, { code: "service_unavailable", detail: "Second unavailable" }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Reads() {
    const a = useQuery({ queryKey: ["first"], queryFn: first });
    const b = useQuery({ queryKey: ["second"], queryFn: second });
    return <QueryErrors queries={[a, b]} />;
  }
  render(<QueryClientProvider client={client}><Reads /></QueryClientProvider>);
  await waitFor(() => expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(2));
  fireEvent.click(screen.getAllByRole("button", { name: "Retry" })[0]);
  await waitFor(() => expect(first).toHaveBeenCalledTimes(2));
  expect(second).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getAllByRole("button", { name: "Retry" })[1]);
  await waitFor(() => expect(second).toHaveBeenCalledTimes(2));
  for (const key of ["first", "second"]) {
    const error = client.getQueryState([key])?.error as StructuredApiError;
    expect({ status: error.status, code: error.code }).toEqual({ status: 503, code: "service_unavailable" });
  }
});

it.each([{ status: 403, code: "permission_denied" }, { status: 404, code: "module_disabled" }])(
  "keeps the $status/$code refusal explanation even when a resource name is provided", ({ status, code }) => {
    const error = new StructuredApiError(status, { code, detail: "Access refused." });
    const refetch = vi.fn();
    render(<ErrorBlock error={error} resource="API scopes" onRetry={refetch} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Access refused.");
    expect(screen.queryByText(/try again|temporarily unavailable/i)).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect({ status: error.status, code: error.code }).toEqual({ status, code });
    expect(refetch).not.toHaveBeenCalled();
  },
);
