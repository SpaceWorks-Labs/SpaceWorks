import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { PublishingQuestions, publishingSummary, type PublishingAnswers } from "./PublishingQuestions";

const base: PublishingAnswers = { is_public: true, listing: "listed", page_state: "live", registration_audience: "accounts" };

it("asks who can see, find and sign up as radio groups and reports each change", () => {
  const onChange = vi.fn();
  render(<PublishingQuestions answers={base} published onChange={onChange} />);
  expect(screen.getByRole("group", { name: "1. Who can see it?" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "2. Who can find it?" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "3. Who can sign up?" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("radio", { name: /Unlisted/ }));
  expect(onChange).toHaveBeenLastCalledWith({ listing: "unlisted" });
  fireEvent.click(screen.getByRole("radio", { name: /Taken down/ }));
  expect(onChange).toHaveBeenLastCalledWith({ page_state: "offline" });
  fireEvent.click(screen.getByRole("radio", { name: /Only your team/ }));
  expect(onChange).toHaveBeenLastCalledWith({ is_public: false });
});

it("disables 'who can find' while the event is private and hides the page state before publishing", () => {
  render(<PublishingQuestions answers={{ ...base, is_public: false }} published={false} onChange={vi.fn()} />);
  expect(screen.getByRole("radio", { name: /Unlisted/ })).toBeDisabled();
  expect(screen.getByText("A private event is never listed. Make it visible first.")).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Public page" })).not.toBeInTheDocument();
});

it("previews who sees what in one sentence", () => {
  expect(publishingSummary({ ...base, listing: "unlisted" }, true)).toMatch(/hidden from every listing and from search engines/);
  expect(publishingSummary({ ...base, is_public: false }, true)).toMatch(/Only your team/);
  expect(publishingSummary({ ...base, page_state: "offline" }, true)).toMatch(/taken down/);
  expect(publishingSummary(base, false)).toMatch(/listed on the events page/);
});
