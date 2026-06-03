import { type Role, hasRole, resolveMembership } from "@core/api/public/membership";
import type { ReactNode } from "react";
import { useCurrentUser } from "./queries";

/**
 * Renders `children` only when the current user has at least `role` in
 * `orgSlug`. Otherwise renders `fallback` (or nothing). Server-side
 * `require()` is still the source of truth — this is UI hinting only.
 *
 * Role logic lives in `@core/api/public/membership`; this is the declarative
 * render-gate over it. For boolean checks use `useHasRole`/`useMembership`.
 *
 * Suspends via `useCurrentUser` (useSuspenseQuery); must be rendered under
 * a `<Suspense>` boundary — typically the app shell provides one.
 */
export function RequireMembership(props: {
  orgSlug: string;
  minRole: Role;
  fallback?: ReactNode;
  children: ReactNode;
}): ReactNode {
  const { data } = useCurrentUser();
  return hasRole(resolveMembership(data, props.orgSlug), props.minRole)
    ? props.children
    : (props.fallback ?? null);
}
