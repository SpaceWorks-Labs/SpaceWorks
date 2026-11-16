import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { undoShortcut, useUndoHistory, useUndoShortcuts } from "./undoHistory";

function key(init: KeyboardEventInit, target?: HTMLElement) {
  const event = new KeyboardEvent("keydown", init);
  if (target) Object.defineProperty(event, "target", { value: target });
  return event;
}

describe("shared undo/redo", () => {
  it("maps Ctrl/Cmd+Z, Shift+Ctrl/Cmd+Z and Ctrl+Y, and ignores typing in fields", () => {
    expect(undoShortcut(key({ key: "z", ctrlKey: true }))).toBe("undo");
    expect(undoShortcut(key({ key: "Z", metaKey: true, shiftKey: true }))).toBe("redo");
    expect(undoShortcut(key({ key: "y", ctrlKey: true }))).toBe("redo");
    expect(undoShortcut(key({ key: "z" }))).toBeNull();
    expect(undoShortcut(key({ key: "z", ctrlKey: true }, document.createElement("input")))).toBeNull();
  });

  it("undoes and redoes whole snapshots and keeps at most the limit", () => {
    const { result } = renderHook(() => {
      const [value, setValue] = useState(0);
      const history = useUndoHistory(value, setValue, 3);
      return { value, history, change: (next: number) => { history.record(value); setValue(next); } };
    });
    for (const next of [1, 2, 3, 4, 5]) act(() => result.current.change(next));
    act(() => result.current.history.undo());
    act(() => result.current.history.undo());
    act(() => result.current.history.undo());
    expect(result.current.value).toBe(2);
    expect(result.current.history.canUndo).toBe(false);
    act(() => result.current.history.redo());
    expect(result.current.value).toBe(3);
    act(() => result.current.change(9));
    expect(result.current.history.canRedo).toBe(false);
  });

  it("binds the shortcuts to the window while enabled", () => {
    function Probe() {
      const [count, setCount] = useState(0);
      useUndoShortcuts(() => setCount((value) => value - 1), () => setCount((value) => value + 1));
      return <p>{count}</p>;
    }
    render(<Probe />);
    fireEvent.keyDown(window, { key: "z", ctrlKey: true });
    fireEvent.keyDown(window, { key: "y", ctrlKey: true });
    fireEvent.keyDown(window, { key: "y", ctrlKey: true });
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});
