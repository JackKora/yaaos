import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StageIndicator, type TicketStage } from "../StageIndicator";

/**
 * Smoke tests for StageIndicator. Pure-render component, no hooks — just
 * cover the three branches: hidden when empty, single-stage line, and
 * multi-stage chronological ordering.
 */

function stage(name: string, state: string, attempts = 1): TicketStage {
  return {
    name,
    state,
    attempt_count: attempts,
    current_attempt: attempts,
    started_at: null,
    completed_at: null,
    workflow_execution_id: `wfx-${name}`,
  };
}

describe("StageIndicator", () => {
  it("renders nothing when stages is empty", () => {
    const { container } = render(<StageIndicator stages={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when stages is undefined", () => {
    const { container } = render(<StageIndicator stages={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a single stage with name + state label", () => {
    render(<StageIndicator stages={[stage("review", "running")]} />);
    expect(screen.getByTestId("stage-indicator")).toBeInTheDocument();
    expect(screen.getByTestId("stage-review")).toHaveTextContent(/review/i);
    expect(screen.getByTestId("stage-review")).toHaveTextContent(/Running/);
  });

  it("renders multi-stage in chronological order (backend returns newest-first)", () => {
    render(
      <StageIndicator
        stages={[
          // newest first (the wire format)
          stage("rereview", "running"),
          stage("review", "done"),
        ]}
      />,
    );
    const chips = screen.getAllByTestId(/^stage-(review|rereview)$/);
    expect(chips[0]).toHaveTextContent(/review/i);
    expect(chips[1]).toHaveTextContent(/rereview/i);
  });

  it("surfaces attempt count when > 1", () => {
    render(<StageIndicator stages={[stage("review", "failed", 2)]} />);
    expect(screen.getByTestId("stage-review")).toHaveTextContent(/Attempt 2\/2/);
  });
});
