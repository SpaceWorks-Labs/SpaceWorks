import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PasswordInput } from "./PasswordInput";

describe("password visibility", () => {
  it("reveals and conceals the existing value without submitting", () => {
    render(<form><label htmlFor="password">Password</label><PasswordInput id="password" defaultValue="kept-secret" /></form>);
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveValue("kept-secret");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(input).toHaveAttribute("type", "password");
  });
});
