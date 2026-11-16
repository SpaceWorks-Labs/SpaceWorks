import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SubmissionEditor } from "./SubmissionEditor";
import { useSubmission, useSubmissionCommand } from "./api";

vi.mock("./api", () => ({ useSubmission: vi.fn(), useSubmissionCommand: vi.fn() }));
const scope = { accountId: 18, makerspaceId: 9, eventId: 42, teamId: 7 };
const mutateAsync = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useSubmission).mockReturnValue({ data: { id: null, event_id: 42, version: 0, state: "draft",
    project: {}, snapshot_id: null, allowed_actions: ["save"] }, isLoading: false, isError: false } as ReturnType<typeof useSubmission>);
  vi.mocked(useSubmissionCommand).mockReturnValue({ mutateAsync, isPending: false, isError: false } as unknown as ReturnType<typeof useSubmissionCommand>);
  mutateAsync.mockResolvedValue({ id: 1, version: 2, state: "draft" });
});

function page() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SubmissionEditor scope={scope} uploadOrigins={[]} formats={[]} /></QueryClientProvider>);
}

describe("maker project draft", () => {
  it("does not submit an unsaved draft or invent public consent", async () => {
    page();
    expect(screen.getByRole("button", { name: "Submit project" })).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Project title" }), { target: { value: "Workshop sensor" } });
    expect(screen.getByText("You have unsaved changes.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
    const body = mutateAsync.mock.calls[0][0];
    expect(body).toMatchObject({ action: "save", version: 0, project: { title: "Workshop sensor", public_requested: false,
      ai_declaration: { used: false, details: "" }, public_asset_ids: [] } });
    expect(body.operationId).toMatch(/^[0-9a-f-]{36}$/);
  });
  it("defers initial file upload until a stable project version exists", () => {
    page();
    expect(screen.getByText("Save your project draft to start uploading files.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Upload file" })).toBeDisabled();
  });
});
