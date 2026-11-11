import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { localeSource, setExplicitLocale } from "../../lib/i18n";
import { expectNoA11yViolations } from "../../test/axe";
import { LanguageSwitcher } from "./LanguageSwitcher";

afterEach(() => setExplicitLocale(null));

describe("LanguageSwitcher", () => {
  it("lists the registry: one English entry, checked, no dead option", async () => {
    render(<LanguageSwitcher />);
    const trigger = screen.getByRole("button", { name: "Language: English" });
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    fireEvent.click(trigger);
    const items = screen.getAllByRole("menuitemradio");
    expect(items.map((item) => item.textContent)).toEqual(["English✓"]);
    await waitFor(() => expect(items[0]).toHaveFocus());
    expect(items[0]).toHaveAttribute("aria-checked", "true");
    expect(items[0]).toHaveAttribute("lang", "en");
  });

  it("is keyboard operable and returns focus on Escape", () => {
    render(<LanguageSwitcher />);
    const trigger = screen.getByRole("button", { name: "Language: English" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(screen.getByRole("menu", { name: "Choose a language" })).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("stores an explicit choice and saves it to the account", async () => {
    const persist = vi.fn().mockResolvedValue(undefined);
    render(<LanguageSwitcher onPersist={persist} />);
    fireEvent.click(screen.getByRole("button", { name: "Language: English" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: /English/ }));
    await waitFor(() => expect(persist).toHaveBeenCalledWith("en"));
    expect(localeSource()).toBe("explicit");
  });

  it("reports a failed account save without losing the browser choice", async () => {
    render(<LanguageSwitcher variant="select" onPersist={() => Promise.reject(new Error("x"))} />);
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "en" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be saved");
    expect(localeSource()).toBe("explicit");
  });

  it("has no axe violations in either variant", async () => {
    const { container, unmount } = render(<LanguageSwitcher />);
    fireEvent.click(screen.getByRole("button", { name: "Language: English" }));
    await expectNoA11yViolations(container);
    unmount();
    const select = render(<LanguageSwitcher variant="select" />);
    await expectNoA11yViolations(select.container);
  });
});
