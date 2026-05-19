import { apiFetch, getCurrentOrgSlug } from "@core/api";
import { Card, CardContent, CardHeader } from "@shared/components";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

interface AuditRow {
  id: string;
  entity_kind: string;
  entity_id: string;
  kind: string;
  payload: Record<string, unknown>;
  actor_kind: string;
  actor_user_id: string | null;
  actor_login: string | null;
  created_at: string;
}

function useAudit(filters: { actor_kind?: string; action?: string }) {
  const slug = getCurrentOrgSlug();
  const params = new URLSearchParams();
  if (filters.actor_kind) params.set("actor_kind", filters.actor_kind);
  if (filters.action) params.set("action", filters.action);
  return useQuery<AuditRow[]>({
    queryKey: ["audit", slug, filters],
    queryFn: () => apiFetch<AuditRow[]>(`/api/audit?${params.toString()}`),
    enabled: !!slug,
  });
}

/**
 * Owner/Admin-only org audit feed. Server-side `require(AUDIT_READ)`
 * enforces Admin minimum; the UI doesn't pre-filter — a Member who
 * navigates here just sees a 403.
 */
export function AuditPage() {
  const [actorKind, setActorKind] = useState("");
  const [action, setAction] = useState("");
  const { data, isLoading, error } = useAudit({ actor_kind: actorKind, action });

  return (
    <div className="mx-auto max-w-[1100px] flex flex-col gap-4 p-6">
      <h1 className="text-[20px] font-semibold tracking-tight">Audit</h1>
      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Filters</h2>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 items-center text-sm">
            <label className="flex items-center gap-1">
              actor
              <select
                value={actorKind}
                onChange={(e) => setActorKind(e.target.value)}
                className="border rounded px-2 py-1"
              >
                <option value="">all</option>
                <option value="user">user</option>
                <option value="workspace">workspace</option>
                <option value="system">system</option>
                <option value="sso">sso</option>
              </select>
            </label>
            <label className="flex items-center gap-1">
              action
              <input
                value={action}
                onChange={(e) => setAction(e.target.value)}
                placeholder="e.g. invited"
                className="border rounded px-2 py-1"
              />
            </label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {isLoading && <p className="text-text-3 text-xs">Loading…</p>}
          {error && (
            <p className="text-red-500 text-xs">{(error as Error).message ?? "Failed to load"}</p>
          )}
          {data && (
            <table className="w-full text-sm">
              <thead className="text-text-3 text-[11.5px] uppercase">
                <tr>
                  <th className="text-left py-1">Time</th>
                  <th className="text-left py-1">Actor</th>
                  <th className="text-left py-1">Action</th>
                  <th className="text-left py-1">Entity</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id} className="border-t">
                    <td className="py-2 mono text-xs">{r.created_at}</td>
                    <td className="py-2">
                      {r.actor_kind}
                      {r.actor_login ? ` (${r.actor_login})` : ""}
                    </td>
                    <td className="py-2 mono">{r.kind}</td>
                    <td className="py-2 mono text-xs">
                      {r.entity_kind}:{r.entity_id.slice(0, 8)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
