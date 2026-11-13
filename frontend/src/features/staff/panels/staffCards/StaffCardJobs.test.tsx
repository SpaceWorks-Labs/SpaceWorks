// Staff ID card bulk output (decision 344(b)): the first print sheet can be previewed before the job is queued,
// from the same preview route family as member, programme and event cards.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../../lib/api")>()), ...api }));

import { StaffCardJobs } from "./StaffCardJobs";

it("previews the first staff-card sheet before starting the job", async () => {
  api.staffRequest.mockImplementation(async (path: string) => (path.endsWith("/preview")
    ? { total: 3, per_page: 10, sheets: 1, paper: "a4", order: "duplex", front: "data:image/png;base64,AA", back: null, mixed_sizes: false }
    : []));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><StaffCardJobs makerspaceId={4} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Preview the first sheet" }));
  await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith(expect.stringMatching(/staff-card-jobs\/preview$/), expect.objectContaining({ method: "POST" })));
  expect(await screen.findByText((text) => /3 cards on 1 sheet/.test(text))).toBeInTheDocument();
});
