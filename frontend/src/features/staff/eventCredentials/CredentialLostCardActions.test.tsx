import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CredentialLostCardActions } from "./CredentialLostCardActions";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const show = (version?: number) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
  <CredentialLostCardActions eventId={3} registrationId={41} version={version} /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("CredentialLostCardActions", () => {
  it("replaces a lost QR after confirmation, against the event version", async () => {
    staffRequest.mockResolvedValue({ id: 9, event_id: 3, version: 6, state: "applied", credential_generation: 2 });
    show(5);
    fireEvent.click(screen.getByRole("button", { name: "Replace QR" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Replace QR" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/events/3/registrations/41/credential/rotate/",
      expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(staffRequest.mock.calls[0][1].body);
    expect(body.expected_version).toBe(5);
    expect(body.operation_id).toMatch(/^[0-9a-f-]{36}$/);
    expect(await screen.findByText("New QR issued.")).toBeInTheDocument();
  });

  it("is disabled until the event version is known", () => {
    show(undefined);
    expect(screen.getByRole("button", { name: "Disable QR" })).toBeDisabled();
  });
});
