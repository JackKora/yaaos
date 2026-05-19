import { apiFetch } from "@core/api";
import { Badge, Button, Card, CardContent, CardHeader } from "@shared/components";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

interface SsoConfig {
  enabled: boolean;
  jit_enabled: boolean;
  exempt_owner_user_id: string | null;
  updated_at?: string | null;
}

function useSsoConfig() {
  return useQuery<SsoConfig>({
    queryKey: ["sso", "config"],
    queryFn: () => apiFetch<SsoConfig>("/api/sso/config"),
  });
}

function useUpsertSsoConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      idp_metadata_xml: string;
      jit_enabled: boolean;
      enabled: boolean;
      exempt_owner_user_id: string | null;
    }) =>
      apiFetch<SsoConfig>("/api/sso/config", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sso", "config"] }),
  });
}

/**
 * Owner-only SSO config page. Lets the operator paste IdP metadata XML,
 * toggle JIT, and pick an exempt Owner (only Owners with a verified TOTP
 * secret are accepted server-side). Hand the IdP the `/api/sso/<slug>/metadata`
 * URL to register yaaos as the SP.
 */
export function SsoConfigPage() {
  const { data, isLoading } = useSsoConfig();
  const upsert = useUpsertSsoConfig();

  const [metadata, setMetadata] = useState("");
  const [jit, setJit] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [exemptOwnerId, setExemptOwnerId] = useState("");

  if (isLoading) return <div className="p-6">Loading…</div>;

  return (
    <div className="mx-auto max-w-[900px] p-6 flex flex-col gap-4">
      <h1 className="text-[20px] font-semibold tracking-tight">SAML SSO</h1>

      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Current state</h2>
        </CardHeader>
        <CardContent>
          <div className="text-sm flex gap-2 items-center">
            <span>Enabled:</span>
            <Badge variant={data?.enabled ? "success" : "soft"}>
              {data?.enabled ? "on" : "off"}
            </Badge>
            <span className="ml-4">JIT:</span>
            <Badge variant={data?.jit_enabled ? "success" : "soft"}>
              {data?.jit_enabled ? "on" : "off"}
            </Badge>
          </div>
          <p className="text-text-3 text-xs mt-2">
            Hand the IdP this URL as the SP entity / ACS:{" "}
            <code className="mono">/api/sso/&lt;your-slug&gt;/metadata</code>
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="font-semibold text-[13.5px]">Update config</h2>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-2 text-sm"
            onSubmit={(e) => {
              e.preventDefault();
              upsert.mutate({
                idp_metadata_xml: metadata,
                jit_enabled: jit,
                enabled,
                exempt_owner_user_id: exemptOwnerId || null,
              });
            }}
          >
            <label className="flex flex-col gap-1">
              IdP metadata XML
              <textarea
                value={metadata}
                onChange={(e) => setMetadata(e.target.value)}
                className="border rounded px-2 py-1 mono text-xs"
                rows={8}
                placeholder="<EntityDescriptor>...</EntityDescriptor>"
                required
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
              />
              Enable SSO for this org
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={jit} onChange={(e) => setJit(e.target.checked)} />
              JIT-create memberships on first SSO login
            </label>
            <label className="flex flex-col gap-1">
              Exempt Owner user id (must have verified 2FA)
              <input
                value={exemptOwnerId}
                onChange={(e) => setExemptOwnerId(e.target.value)}
                className="border rounded px-2 py-1 mono text-xs"
                placeholder="(none)"
              />
            </label>
            <div>
              <Button type="submit" disabled={upsert.isPending} data-testid="sso-save">
                {upsert.isPending ? "Saving…" : "Save"}
              </Button>
            </div>
            {upsert.isError && (
              <p className="text-red-500 text-xs">
                {(upsert.error as Error)?.message ?? "Save failed"}
              </p>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
