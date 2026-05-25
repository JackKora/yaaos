import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

/**
 * Smoke tests for the Org Picker. Mocks the two backend hooks
 * (`useMyOrgs`, `useCreateOrg`) and asserts the three branches: empty
 * list, populated list, create-modal open.
 */

const createMutate = vi.fn();

vi.mock("@core/api", () => ({
  useMyOrgs: () => useMyOrgsMock(),
  useCreateOrg: () => ({
    mutate: createMutate,
    isPending: false,
    error: null,
    data: undefined,
    reset: vi.fn(),
  }),
}));

vi.mock("@tanstack/react-router", () => ({
  // Stub `Link` so it renders a plain `<a>` — production code uses it for
  // SPA nav, assertions here only check the rendered href.
  Link: ({
    to,
    params,
    children,
    ...props
  }: {
    to: string;
    params?: Record<string, string>;
    children: React.ReactNode;
  } & Record<string, unknown>) => {
    const href = params
      ? Object.entries(params).reduce((acc, [k, v]) => acc.replace(`$${k}`, v), to)
      : to;
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  },
}));

let useMyOrgsMock = () => ({ data: [] as unknown[], isLoading: false });

import { OrgPickerPage } from "../OrgPickerPage";

describe("OrgPickerPage", () => {
  it("renders the EmptyState when there are no orgs", () => {
    useMyOrgsMock = () => ({ data: [], isLoading: false });
    render(<OrgPickerPage />);
    expect(screen.getByText(/don't belong to any organizations yet/i)).toBeInTheDocument();
  });

  it("renders one row per org with the role badge", () => {
    useMyOrgsMock = () =>
      ({
        data: [
          { id: "o1", slug: "alpha", name: "Alpha", role: "admin", last_used_at: null },
          { id: "o2", slug: "beta", name: "Beta", role: "builder", last_used_at: null },
        ],
        isLoading: false,
      }) as ReturnType<typeof useMyOrgsMock>;
    render(<OrgPickerPage />);
    expect(screen.getByTestId("org-picker-row-alpha")).toHaveTextContent("Alpha");
    expect(screen.getByTestId("org-picker-row-alpha")).toHaveTextContent("Admin");
    expect(screen.getByTestId("org-picker-row-beta")).toHaveTextContent("Beta");
    expect(screen.getByTestId("org-picker-row-beta")).toHaveTextContent("Builder");
  });

  it("Create button opens the modal + submit fires useCreateOrg", () => {
    useMyOrgsMock = () => ({ data: [], isLoading: false });
    createMutate.mockReset();
    render(<OrgPickerPage />);
    fireEvent.click(screen.getByTestId("org-picker-create"));
    fireEvent.change(screen.getByTestId("create-org-name"), { target: { value: "New Org" } });
    fireEvent.change(screen.getByTestId("create-org-slug"), { target: { value: "new-org" } });
    fireEvent.click(screen.getByTestId("create-org-submit"));
    expect(createMutate).toHaveBeenCalledWith(
      { name: "New Org", slug: "new-org" },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });
});
