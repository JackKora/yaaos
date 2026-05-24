import type { ReactNode } from "react";
import { useCurrentUser } from "./queries";

type Role = "owner" | "admin" | "builder";

const RANK: Record<Role, number> = { builder: 0, admin: 1, owner: 2 };

/**
 * Renders `children` only when the current user has at least `role` in
 * `orgSlug`. Otherwise renders `fallback` (or nothing). Server-side
 * `require()` is still the source of truth — this is UI hinting only.
 */
export function RequireMembership(props: {
  orgSlug: string;
  role: Role;
  fallback?: ReactNode;
  children: ReactNode;
}): ReactNode {
  const { data, isLoading } = useCurrentUser();
  if (isLoading) return null;
  if (!data) return props.fallback ?? null;
  const membership = data.memberships.find((m) => m.slug === props.orgSlug);
  if (!membership) return props.fallback ?? null;
  if (RANK[membership.role] < RANK[props.role]) return props.fallback ?? null;
  return props.children;
}
