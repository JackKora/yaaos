/**
 * Centralized UI role-gating primitive.
 *
 * One definition of the role rank order, one membership resolver, and the
 * hooks every UI role check goes through. Render-gating uses
 * `<RequireMembership>` (domain/auth, wraps this); boolean checks use
 * `useHasRole` / `useMembership`. Lives in core/api so both `core/*` and
 * `domain/*` may import it (core must not import domain).
 *
 * This is a UI hint only — the backend `require(action)` is the authority.
 */
import { type CurrentUser, type MembershipSummary, useCurrentUser } from "./queries";

export type Role = MembershipSummary["role"];

/** builder < admin < owner. The single source of truth for role ordering. */
export const ROLE_RANK: Record<Role, number> = { builder: 0, admin: 1, owner: 2 };

/** The current user's membership in `orgSlug`, or null if none / no slug / signed out. */
export function resolveMembership(
  user: CurrentUser | null,
  orgSlug: string | null | undefined,
): MembershipSummary | null {
  if (!user || !orgSlug) return null;
  return user.memberships.find((m) => m.slug === orgSlug) ?? null;
}

/** True when `membership` exists and meets or exceeds `minRole`. */
export function hasRole(membership: MembershipSummary | null, minRole: Role): boolean {
  if (!membership) return false;
  return ROLE_RANK[membership.role] >= ROLE_RANK[minRole];
}

/** The current user's membership in `orgSlug` (null if none). Suspends via useCurrentUser. */
export function useMembership(orgSlug: string | null | undefined): MembershipSummary | null {
  const { data } = useCurrentUser();
  return resolveMembership(data, orgSlug);
}

/** True when the current user has at least `minRole` in `orgSlug`. Suspends via useCurrentUser. */
export function useHasRole(orgSlug: string | null | undefined, minRole: Role): boolean {
  return hasRole(useMembership(orgSlug), minRole);
}
