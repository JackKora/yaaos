/** Mirror of the backend `PluginMeta` payload from `GET /api/plugins/available`. */
export interface PluginMeta {
  id: string;
  type: "vcs" | "coding_agent" | "workspace";
  display_name: string;
  description: string | null;
  docs_url: string | null;
}
