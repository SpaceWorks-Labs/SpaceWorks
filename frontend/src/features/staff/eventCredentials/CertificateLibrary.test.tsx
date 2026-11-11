import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import fixture from "../../../../../backend/tests/events/programme/contracts/fixtures/template-seed-v2.json";
import type { LayerDocument } from "./layout";
import { CertificateLibrary } from "./CertificateLibrary";

const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
beforeEach(() => { request.mockReset(); request.mockResolvedValue({ results: [] }); });

it("copies an immutable event revision rather than sending foreign resource IDs as library-owned images", async () => {
  render(<QueryClientProvider client={new QueryClient()}><CertificateLibrary makerspaceId={1} eventId={42}
    eventRevisionId={9} eventVersion={4} document={fixture.seed.document as LayerDocument} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Template name"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Copy saved event revision with all artwork" }));
  await waitFor(() => expect(request.mock.calls.some((row) => row[1]?.method === "POST")).toBe(true));
  const call = request.mock.calls.find((row) => row[1]?.method === "POST")!;
  expect(call[0]).toContain("from-event/");
  expect(JSON.parse(call[1].body)).toMatchObject({ name: "Workshop", event_id: 42, revision_id: 9, expected_version: 0, template_id: null });
  expect(call[1].body).not.toContain("resource_id");
});
