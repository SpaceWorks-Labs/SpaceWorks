import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { MemberAuthPanel } from "./MemberAuthPanel";

const { publicV1Request, staffRequest } = vi.hoisted(() => ({ publicV1Request: vi.fn(), staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ publicV1Request, staffRequest, setAccessToken: vi.fn() }));
vi.mock("../auth/SocialSignInButtons", () => ({ SocialSignInButtons: () => null }));
beforeEach(() => {
  publicV1Request.mockReset(); staffRequest.mockReset();
  publicV1Request.mockImplementation((path: string) => Promise.resolve(path === "/config" ? {} : { access: "verification", surface: "verification_only" }));
});

it("ignores repeated Enter submissions while email verification is pending", async () => {
  staffRequest.mockImplementation(() => new Promise(() => {}));
  const view = render(<MemberAuthPanel onAuthenticated={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "member@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Verify your email" })).toBeVisible();
  fireEvent.change(screen.getByLabelText("Verification code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify email" }));
  await waitFor(() => expect(screen.getByRole("button", { name: /Please wait/ })).toBeDisabled());
  fireEvent.submit(view.container.querySelector("form")!);
  fireEvent.submit(view.container.querySelector("form")!);
  expect(staffRequest).toHaveBeenCalledTimes(1);
  expect(staffRequest).toHaveBeenCalledWith("/auth/email-verification/confirm", { method: "POST", body: JSON.stringify({ code: "123456" }) });
});
