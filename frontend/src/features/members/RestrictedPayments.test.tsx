import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { memberRequest, StructuredApiError } from "../../lib/api";
import { RestrictedPayments } from "./RestrictedPayments";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), memberRequest: vi.fn() }));
vi.mock("./MemberPayments", () => ({ MemberPaymentRows: () => <p>Own charges</p> }));
beforeEach(() => vi.mocked(memberRequest).mockReset());
function show(id = 7) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <RestrictedPayments makerspaceId={id} name={"Very long makerspace name ".repeat(20)} />
  </QueryClientProvider>);
}

it("shows loading followed by an empty money state", async () => {
  let done!: (rows: []) => void;
  vi.mocked(memberRequest).mockReturnValue(new Promise(resolve => { done = resolve; }));
  show();
  expect(screen.getByRole("status", { name: "Loading payments..." })).toBeVisible();
  done([]);
  expect(await screen.findByText("Nothing to pay. You are all settled.")).toBeVisible();
});

it.each([403, 404, 503])("shows a retryable %i refusal without cached charges", async status => {
  vi.mocked(memberRequest).mockRejectedValueOnce(new StructuredApiError(status, { detail: "Charges unavailable" }))
    .mockResolvedValue([{ id: 1 }]);
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(status === 404
    ? "This charge is no longer waiting for payment. Refresh to see its latest status." : "Charges unavailable");
  expect(screen.queryByText("Own charges")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("Own charges")).toBeVisible();
});

it("does not request another space when tenant bootstrap failed", async () => {
  show(-1);
  expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your makerspace. Try again.");
  expect(memberRequest).not.toHaveBeenCalled();
});
