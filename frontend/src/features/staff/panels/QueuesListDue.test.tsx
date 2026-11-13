import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { RequestList } from "./QueuesList";

vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn() }));

const inTwoDays = new Date(Date.now() + 2.2 * 86400000).toISOString();
const row = (id: number, status: string) => ({ id, status, requester_username: `user${id}`, requester_display: `User ${id}`,
  items: [], return_due_at: inTwoDays }) as never;

function mount(rows: unknown[]) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><RequestList rows={rows as never} /></MemoryRouter></QueryClientProvider>);
}

it("shows a mid-sentence due line only while the request still holds hardware", () => {
  mount([row(1, "issued"), row(2, "returned"), row(3, "closed_with_issue")]);
  expect(screen.getAllByText(/^Due/)).toHaveLength(1);
  expect(screen.getByText("in 2 days")).toBeInTheDocument();
  expect(screen.queryByText("In 2 days")).not.toBeInTheDocument();
});
