import { useCurrentUser } from "@domain/auth";

/** Red banner shown when the current org has one or more broken MCP integrations.
 *  Owners + Admins only (the backend zeros the list for Members). Click deep-links
 *  to the Integrations settings page (added in Phase 4 — until then the user
 *  lands on the settings shell, which routes them to the right place). */
export function BrokenIntegrationsBanner() {
  const { data } = useCurrentUser();
  if (!data) return null;
  const currentOrg = data.orgs.find((o) => o.slug === data.current_org_slug);
  if (!currentOrg || currentOrg.broken_integrations.length === 0) return null;
  const providers = currentOrg.broken_integrations.map((b) => b.provider).join(", ");
  return (
    <a
      href={`/orgs/${currentOrg.slug}/settings/integrations`}
      className="block bg-red-100 border-b border-red-300 text-red-900 px-4 py-2 text-sm hover:bg-red-200"
      data-testid="broken-integrations-banner"
    >
      <span className="font-semibold">MCP integration disconnected:</span> {providers}. Reconnect in
      Org Settings → Integrations.
    </a>
  );
}
