export { AuditSettingsPage } from "./AuditSettingsPage";
export { AuthSettingsPage } from "./AuthSettingsPage";
export { CodingAgentSettingsPage } from "./coding_agents/CodingAgentSettingsPage";
export { CodingAgentsSettingsPage } from "./coding_agents/CodingAgentsSettingsPage";
// Side-effect import: registers the bespoke claude_code component in the
// plugin registry at module load (Phase 10).
import "./coding_agents/plugins/claude_code";
export {
  type PluginSettingsComponent,
  type PluginSettingsComponentProps,
  getPluginSettingsComponent,
  registerPluginSettingsComponent,
} from "./coding_agents/plugin_registry";
export { MembersSettingsPage } from "./MembersSettingsPage";
export { OrgSettingsLayout } from "./OrgSettingsLayout";
export { PlaceholderSettingsPage } from "./PlaceholderSettingsPage";
export { VcsSettingsPage } from "./vcs/VcsSettingsPage";
