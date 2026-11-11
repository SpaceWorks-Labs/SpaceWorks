import { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { withEventSession } from "./EventSessionBoundary";
import type { EventScope } from "./privateQueries";
const Editor = withEventSession(function Editor({ scope }: { scope: EventScope }) {
  const [draft, setDraft] = useState("");
  return <input aria-label={`Draft ${scope.actorId}`} value={draft} onChange={event => setDraft(event.target.value)} />;
});
describe("private route local-state lifecycle", () => {
  it("discards a draft when actor or event changes", () => {
    const scope = { actorId: 1, makerspaceId: 2, eventId: 41 };
    const { rerender } = render(<Editor scope={scope} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "private draft" } });
    rerender(<Editor scope={{ ...scope, actorId: 3 }} />);
    expect(screen.getByRole("textbox")).toHaveValue("");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "another draft" } });
    rerender(<Editor scope={{ ...scope, actorId: 3, eventId: 42 }} />);
    expect(screen.getByRole("textbox")).toHaveValue("");
  });
});
