/**
 * Current org slug — derived from the URL on every read. The URL path is
 * the only source of truth: `/orgs/$slug/...` ⇒ `$slug`; everything else
 * (including `/login`, `/orgs` picker, and any non-org route) ⇒ `null`.
 *
 * There is no module-global cache. Two browser tabs in different orgs
 * stay independent because each reads its own `window.location`.
 *
 * `getCurrentOrgSlug()` is a plain function for `apiFetch` (no React
 * context available); `useCurrentOrgSlug()` is the reactive hook chrome
 * components use — it re-renders on SPA navigation via TanStack Router.
 */
import { useRouterState } from "@tanstack/react-router";

const ORG_PATH_RE = /^\/orgs\/([^/]+)/;

function extractSlug(pathname: string): string | null {
  const m = pathname.match(ORG_PATH_RE);
  if (!m) return null;
  const slug = m[1];
  // `/orgs` (the picker, no slug after it) and stale "undefined"/"null"
  // strings from earlier-bug URLs both resolve to no-slug.
  if (!slug || slug === "undefined" || slug === "null") return null;
  return slug;
}

export function getCurrentOrgSlug(): string | null {
  if (typeof window === "undefined") return null;
  return extractSlug(window.location.pathname);
}

export function useCurrentOrgSlug(): string | null {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return extractSlug(pathname);
}
