import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HitlPanel } from "../HitlPanel";

/**
 * HITL panel — discriminated-union renderer.
 *
 * One smoke test per `kind` covers the three known shapes + the fallback
 * for unknown/missing kinds.
 */

describe("HitlPanel", () => {
  it("renders choice buttons and reports the chosen value on click", () => {
    const onSubmit = vi.fn();
    render(
      <HitlPanel
        payload={{
          kind: "choice",
          title: "Continue?",
          body: "Cost ~5 cents.",
          options: [
            { value: "yes", label: "Yes" },
            { value: "no", label: "No", variant: "destructive" },
          ],
        }}
        onSubmit={onSubmit}
      />,
    );
    expect(screen.getByTestId("hitl-panel")).toBeInTheDocument();
    expect(screen.getByText("Continue?")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("hitl-choice-yes"));
    expect(onSubmit).toHaveBeenCalledWith({ choice: "yes" });
  });

  it("renders text prompt and submits the typed value", () => {
    const onSubmit = vi.fn();
    render(
      <HitlPanel
        payload={{ kind: "text", title: "Why?", body: "", placeholder: "type here" }}
        onSubmit={onSubmit}
      />,
    );
    const input = screen.getByTestId("hitl-text-input");
    fireEvent.change(input, { target: { value: "because" } });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));
    expect(onSubmit).toHaveBeenCalledWith({ text: "because" });
  });

  it("disables submit until required form fields are filled", () => {
    const onSubmit = vi.fn();
    render(
      <HitlPanel
        payload={{
          kind: "form",
          title: "Approve?",
          body: "",
          fields: [{ name: "reason", label: "Reason", type: "text", required: true }],
        }}
        onSubmit={onSubmit}
      />,
    );
    const submit = screen.getByRole("button", { name: /submit/i });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByTestId("hitl-field-reason"), { target: { value: "ok" } });
    expect(submit).not.toBeDisabled();
    fireEvent.click(submit);
    expect(onSubmit).toHaveBeenCalledWith({ reason: "ok" });
  });

  it("falls back to free-text when kind is missing/unknown", () => {
    const onSubmit = vi.fn();
    render(
      <HitlPanel payload={{ body: "Plain markdown body — no schema." }} onSubmit={onSubmit} />,
    );
    const panel = screen.getByTestId("hitl-panel");
    expect(panel).toHaveAttribute("data-hitl-fallback", "true");
    fireEvent.change(screen.getByTestId("hitl-text-input"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));
    expect(onSubmit).toHaveBeenCalledWith({ text: "hi" });
  });
});
