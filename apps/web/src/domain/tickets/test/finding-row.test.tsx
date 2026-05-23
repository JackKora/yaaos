import type { FindingRow as FindingRowData } from "@core/api";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FindingRow } from "../FindingRow";

/** Minimal fixture shaped like the wire `FindingRow`. */
function fixture(overrides: Partial<FindingRowData> = {}): FindingRowData {
  return {
    id: "f1",
    state: "open",
    severity: "major",
    rule_id: "x/null-deref",
    title: "x could be None",
    body: "caller may pass None",
    rationale: "raises NoneType",
    confidence: 90,
    first_seen_review_id: "r1",
    last_observed_review_id: "r1",
    file_path: "src/foo.py",
    line_start: 10,
    line_end: 10,
    ...overrides,
  };
}

describe("FindingRow", () => {
  it("renders severity, title, file:line", () => {
    render(<FindingRow finding={fixture()} />);
    expect(screen.getByText(/Major/i)).toBeInTheDocument();
    expect(screen.getByText("x could be None")).toBeInTheDocument();
    expect(screen.getByText("src/foo.py:10")).toBeInTheDocument();
  });

  it("Ack button invokes onAck with the finding id when state is open", () => {
    const onAck = vi.fn();
    render(<FindingRow finding={fixture()} onAck={onAck} />);
    fireEvent.click(screen.getByTestId("finding-ack-f1"));
    expect(onAck).toHaveBeenCalledWith("f1");
  });

  it("push-back: requires ≥10 char reason; submit fires with id + reason", () => {
    const onPushBack = vi.fn();
    render(<FindingRow finding={fixture()} onPushBack={onPushBack} />);
    fireEvent.click(screen.getByTestId("finding-pushback-toggle-f1"));
    const reason = screen.getByTestId("finding-pushback-reason-f1");
    const submit = screen.getByTestId("finding-pushback-submit-f1");

    expect(submit).toBeDisabled();
    fireEvent.change(reason, { target: { value: "too short" } });
    expect(submit).toBeDisabled();

    fireEvent.change(reason, { target: { value: "this is a proper reason" } });
    expect(submit).not.toBeDisabled();
    fireEvent.click(submit);
    expect(onPushBack).toHaveBeenCalledWith({
      finding_id: "f1",
      reason: "this is a proper reason",
    });
  });

  it("hides action buttons + shows state label when finding is not open", () => {
    render(<FindingRow finding={fixture({ state: "acknowledged" })} />);
    expect(screen.queryByTestId("finding-ack-f1")).toBeNull();
    expect(screen.queryByTestId("finding-pushback-toggle-f1")).toBeNull();
    expect(screen.getByText("Acked")).toBeInTheDocument();
  });
});
