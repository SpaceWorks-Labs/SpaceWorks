import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { ReportProblem } from "./ReportProblem";
import { TechnicianOptInPage } from "./TechnicianOptInPage";

const api = vi.hoisted(() => ({ memberRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), ...api }));

const wrap = (node: React.ReactNode, path = "/") => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter></QueryClientProvider>);

describe("ReportProblem", () => {
  beforeEach(() => { api.memberRequest.mockReset(); api.publicV1Request.mockReset(); });

  it("asks which item of a multi-item loan and sends the report", async () => {
    api.memberRequest.mockImplementation((path: string) => Promise.resolve(path.includes("loan-items")
      ? [{ product_id: 1, asset_id: null, name: "Drill" }, { product_id: 2, asset_id: 5, name: "Scope (S-1)" }] : { id: 3, state: "reported" }));
    const { container } = wrap(<ReportProblem source={{ makerspace_id: 4, loan_id: 8 }} />);
    fireEvent.click(screen.getByRole("button", { name: "Report a problem" }));
    fireEvent.change(await screen.findByLabelText("Which item"), { target: { value: "2:5" } });
    fireEvent.change(screen.getByLabelText("What's wrong"), { target: { value: "No display" } });
    fireEvent.change(screen.getByLabelText("Details"), { target: { value: "Screen stays dark." } });
    await expectNoA11yViolations(container);
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText(/will email you when it is fixed/)).toBeInTheDocument();
    const [, options] = api.memberRequest.mock.calls.find(([path]) => path === "/member/issues")!;
    expect(JSON.parse(options.body)).toMatchObject({ loan_id: 8, asset_id: 5, title: "No display", photos: [] });
  });
});

describe("TechnicianOptInPage", () => {
  beforeEach(() => { api.publicV1Request.mockReset(); });

  it("records WhatsApp consent and never shows contact details", async () => {
    const page = { makerspace_name: "Lab", technician_name: "Ravi", has_phone: true, telegram_start: "/start abc",
      consent: { email: true, telegram: false, whatsapp: false, sms: false } };
    api.publicV1Request.mockImplementation((_path: string, options?: RequestInit) => Promise.resolve(options?.method === "POST"
      ? { ...page, consent: { ...page.consent, whatsapp: true } } : page));
    wrap(<Routes><Route path="/technician-opt-in/:token" element={<TechnicianOptInPage />} /></Routes>, "/technician-opt-in/abc");
    expect(await screen.findByText("Repair requests for Ravi")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "I agree" }));
    await waitFor(() => expect(screen.getByText(/you agreed to whatsapp/)).toBeInTheDocument());
    expect(api.publicV1Request).toHaveBeenCalledWith("/public/technician-opt-in/abc",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ channels: ["whatsapp"] }) }));
  });
});
