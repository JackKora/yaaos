import { describe, expect, it } from "vitest";
import { ROLE_RANK, hasRole, resolveMembership } from "./membership";
import type { CurrentUser, MembershipSummary } from "./queries";

function membership(slug: string, role: MembershipSummary["role"]): MembershipSummary {
  return { org_id: `org-${slug}`, slug, display_name: slug, role, handle: `@me-${slug}` };
}

function user(...memberships: MembershipSummary[]): CurrentUser {
  return {
    user: { id: "u1", display_name: "Me", primary_email: "me@example.com", emails: [] },
    memberships,
  };
}

describe("ROLE_RANK", () => {
  it("orders builder < admin < owner", () => {
    expect(ROLE_RANK.builder).toBeLessThan(ROLE_RANK.admin);
    expect(ROLE_RANK.admin).toBeLessThan(ROLE_RANK.owner);
  });
});

describe("resolveMembership", () => {
  const u = user(membership("acme", "admin"), membership("beta", "builder"));

  it("returns the membership matching the slug", () => {
    expect(resolveMembership(u, "acme")?.role).toBe("admin");
    expect(resolveMembership(u, "beta")?.role).toBe("builder");
  });
  it("returns null for an unknown slug", () => {
    expect(resolveMembership(u, "nope")).toBeNull();
  });
  it("returns null for a null/empty slug", () => {
    expect(resolveMembership(u, null)).toBeNull();
    expect(resolveMembership(u, "")).toBeNull();
  });
  it("returns null when the user is null", () => {
    expect(resolveMembership(null, "acme")).toBeNull();
  });
});

describe("hasRole", () => {
  it("owner satisfies every gate", () => {
    const m = membership("acme", "owner");
    expect(hasRole(m, "owner")).toBe(true);
    expect(hasRole(m, "admin")).toBe(true);
    expect(hasRole(m, "builder")).toBe(true);
  });
  it("admin satisfies admin and builder, not owner", () => {
    const m = membership("acme", "admin");
    expect(hasRole(m, "owner")).toBe(false);
    expect(hasRole(m, "admin")).toBe(true);
    expect(hasRole(m, "builder")).toBe(true);
  });
  it("builder satisfies only builder", () => {
    const m = membership("acme", "builder");
    expect(hasRole(m, "admin")).toBe(false);
    expect(hasRole(m, "builder")).toBe(true);
  });
  it("null membership never satisfies a gate", () => {
    expect(hasRole(null, "builder")).toBe(false);
  });
});
