import { registerPluginSettingsComponent } from "../../plugin_registry";
import { ClaudeCodeSettings } from "./ClaudeCodeSettings";

registerPluginSettingsComponent("claude_code", ClaudeCodeSettings);

export { ClaudeCodeSettings };
