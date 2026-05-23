import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityEventRow } from "../ActivityEventRow";

function event(kind: string, overrides: Record<string, unknown> = {}) {
  return {
    ts: "2026-05-23T00:00:00Z",
    kind,
    message: "did a thing",
    detail: null,
    ...overrides,
  };
}

describe("ActivityEventRow", () => {
  it("renders the event message + kind label", () => {
    render(<ActivityEventRow event={event("session_start", { message: "agent started" })} />);
    expect(screen.getByText("agent started")).toBeInTheDocument();
    expect(screen.getByTestId("activity-event-row")).toHaveAttribute("data-kind", "session_start");
  });

  it("tool_call_finished with exit_code===0 uses the success icon", () => {
    const { container } = render(
      <ActivityEventRow
        event={event("tool_call_finished", { detail: { exit_code: 0 } }) as never}
      />,
    );
    // success tone applied: text-success class on the icon
    const icon = container.querySelector("svg");
    expect(icon?.getAttribute("class")).toContain("text-success");
  });

  it("tool_call_finished with non-zero exit_code uses the destructive icon", () => {
    const { container } = render(
      <ActivityEventRow
        event={event("tool_call_finished", { detail: { exit_code: 1 } }) as never}
      />,
    );
    const icon = container.querySelector("svg");
    expect(icon?.getAttribute("class")).toContain("text-destructive");
  });

  it("falls back to the generic dot icon for unknown kinds", () => {
    render(<ActivityEventRow event={event("future_unknown_kind") as never} />);
    expect(screen.getByTestId("activity-event-row")).toHaveAttribute(
      "data-kind",
      "future_unknown_kind",
    );
  });

  it("wraps long messages in a <details> for click-to-expand", () => {
    const longMessage = Array.from({ length: 6 }, () => "line").join("\n");
    const { container } = render(
      <ActivityEventRow event={event("assistant_message", { message: longMessage }) as never} />,
    );
    expect(container.querySelector("details")).not.toBeNull();
  });
});
