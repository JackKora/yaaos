// pluginskills.go — helpers for discovering plugin/marketplace skills declared
// in a repo's .claude/settings.json.
//
// The recipe mirrors the architecture's Enumeration recipe §2-3:
//   1. Parse .claude/settings.json for extraKnownMarketplaces + enabledPlugins.
//   2. Per declared marketplace: `claude plugin marketplace add <source>`.
//      Per declared plugin: `claude plugin install <plugin>@<marketplace>`.
//      Each call is independent; on failure log and continue (graceful degrade).
//   3. Scan ~/.claude/plugins/cache/<marketplace>/<plugin>/skills/<skill>/SKILL.md.
//      Handle is namespaced "<plugin>:<skill>"; source="plugin"; plugin_name=<plugin>.
//
// Always-degrade contract: repo-local skills always return; plugin skills are
// best-effort. Zero plugin skills is a success, not a failure.
//
// The same installer is reusable on the review path when a plugin-sourced
// skill is assigned for a review run — the handler enumerates, the recipe
// installs.

package workspace

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/yaaos/agent/internal/command"
)

// claudeSettingsPluginSection mirrors the fields we care about from
// .claude/settings.json. Additional keys are ignored.
type claudeSettingsPluginSection struct {
	// ExtraKnownMarketplaces holds marketplace source URLs declared by the repo.
	// Each entry is a string (the marketplace source URL).
	ExtraKnownMarketplaces []string `json:"extraKnownMarketplaces"`
	// EnabledPlugins holds plugin references in the form "<plugin>@<marketplace>".
	EnabledPlugins []string `json:"enabledPlugins"`
}

// parseClaudeSettings parses the plugin-relevant fields from
// <clonePath>/.claude/settings.json. Returns an empty struct when the file is
// absent or carries no plugin declarations (not an error — the repo simply
// declares no plugins).
func parseClaudeSettings(clonePath string) (claudeSettingsPluginSection, error) {
	settingsPath := filepath.Join(clonePath, ".claude", "settings.json")
	data, err := os.ReadFile(settingsPath)
	if err != nil {
		if os.IsNotExist(err) {
			return claudeSettingsPluginSection{}, nil
		}
		return claudeSettingsPluginSection{}, fmt.Errorf("read settings.json: %w", err)
	}
	var s claudeSettingsPluginSection
	if err := json.Unmarshal(data, &s); err != nil {
		// Malformed JSON: degrade gracefully — log and return empty.
		slog.Warn("pluginskills: malformed .claude/settings.json; skipping plugin discovery",
			"path", settingsPath, "err", err)
		return claudeSettingsPluginSection{}, nil
	}
	return s, nil
}

// pluginRunner is the seam used by InstallPluginSkills to invoke
// `claude plugin <args...>` in the given directory. Production execs the real
// binary via runClaudePluginExec; tests replace this var with a fake that
// records calls and returns canned errors. Replace-and-restore is the test's
// responsibility (use t.Cleanup).
var pluginRunner = runClaudePluginExec

// runClaudePluginExec is the production pluginRunner: execs the real `claude`
// binary. Stdout + stderr are captured; the combined output is included in any
// returned error for operator diagnostics. On non-zero exit the error is
// returned to the caller (who decides whether to degrade or fail).
//
// GIT_ASKPASS is threaded through so private marketplace fetches that share
// the repo's GitHub host can reuse the installation token. The caller sets the
// env before calling; this function inherits it from os.Environ().
func runClaudePluginExec(ctx context.Context, cwd string, args ...string) error {
	argv := append([]string{"plugin"}, args...)
	cmd := exec.CommandContext(ctx, "claude", argv...)
	if cwd != "" {
		cmd.Dir = cwd
	}
	// Inherit the full parent environment so GIT_ASKPASS and HOME are available.
	cmd.Env = os.Environ()
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("claude plugin %s: %w (output: %s)", args[0], err, string(out))
	}
	return nil
}

// InstallPluginSkills parses <clonePath>/.claude/settings.json, runs
// `claude plugin marketplace add` for each declared marketplace and
// `claude plugin install <plugin>@<marketplace>` for each declared plugin,
// then scans ~/.claude/plugins/cache/ for the installed skills.
//
// Each marketplace add and each plugin install is independent: on any failure
// a warning is logged and the install continues (graceful degrade). The
// function always returns whatever plugin skills were successfully installed,
// never an error from a single bad plugin.
//
// gitAskpassEnv is the GIT_ASKPASS=<path> entry to inject into the subprocess
// environment for same-host private marketplace auth. Pass an empty string to
// skip it (for public marketplaces or when the auth token is unavailable).
//
// The installed plugin cache persists in ~/. claude/plugins/cache/ (shared
// agent HOME) — acceptable for a read-only config probe.
func InstallPluginSkills(ctx context.Context, clonePath, gitAskpassEnv string) ([]command.SkillManifestEntry, error) {
	settings, err := parseClaudeSettings(clonePath)
	if err != nil {
		// settings.json unreadable for a non-NotExist reason — log + skip plugin
		// discovery entirely (graceful degrade).
		slog.Warn("pluginskills: could not parse settings.json; skipping plugin discovery",
			"clone_path", clonePath, "err", err)
		return nil, nil
	}
	if len(settings.ExtraKnownMarketplaces) == 0 && len(settings.EnabledPlugins) == 0 {
		// No plugin declarations in this repo.
		return nil, nil
	}

	// Optionally inject GIT_ASKPASS into the subprocess environment. We set it
	// as an os.Setenv before each subprocess call rather than passing per-cmd,
	// because runClaudePlugin inherits os.Environ(). Restore the old value on
	// exit so the agent process state is unmodified after the call.
	if gitAskpassEnv != "" {
		// gitAskpassEnv is expected in the form "GIT_ASKPASS=/path/to/helper"
		// Parse the value part out for os.Setenv.
		const prefix = "GIT_ASKPASS="
		if len(gitAskpassEnv) > len(prefix) && gitAskpassEnv[:len(prefix)] == prefix {
			askpassPath := gitAskpassEnv[len(prefix):]
			old := os.Getenv("GIT_ASKPASS")
			if err := os.Setenv("GIT_ASKPASS", askpassPath); err != nil {
				slog.Warn("pluginskills: could not set GIT_ASKPASS", "err", err)
			} else {
				defer func() {
					if old == "" {
						_ = os.Unsetenv("GIT_ASKPASS")
					} else {
						_ = os.Setenv("GIT_ASKPASS", old)
					}
				}()
			}
		}
	}

	// Step 2a: register each declared marketplace.
	for _, source := range settings.ExtraKnownMarketplaces {
		if err := pluginRunner(ctx, clonePath, "marketplace", "add", source); err != nil {
			slog.Warn("pluginskills: marketplace add failed; skipping",
				"source", source, "err", err)
			// Continue — one bad marketplace does not abort the rest.
		}
	}

	// Step 2b: install each declared plugin.
	for _, pluginRef := range settings.EnabledPlugins {
		if err := pluginRunner(ctx, clonePath, "install", pluginRef); err != nil {
			slog.Warn("pluginskills: plugin install failed; skipping",
				"plugin_ref", pluginRef, "err", err)
			// Continue — one bad plugin does not abort the rest.
		}
	}

	// Step 3: scan the plugin cache for installed skills.
	return scanPluginCacheSkills()
}

// scanPluginCacheSkills walks ~/.claude/plugins/cache/<marketplace>/<plugin>/skills/<skill>/SKILL.md
// and returns one SkillManifestEntry per skill directory that contains a SKILL.md.
// The handle is namespaced "<plugin>:<skill>"; source="plugin"; plugin_name="<plugin>".
//
// A missing or unreadable cache directory returns an empty list (not an error);
// partial results from partially-installed plugins are returned as-is.
func scanPluginCacheSkills() ([]command.SkillManifestEntry, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		slog.Warn("pluginskills: could not determine HOME; skipping plugin cache scan", "err", err)
		return nil, nil
	}
	cacheRoot := filepath.Join(home, ".claude", "plugins", "cache")

	// cache/<marketplace>/<plugin>/skills/<skill>/SKILL.md
	var skills []command.SkillManifestEntry

	// Enumerate marketplaces.
	marketplaces, err := os.ReadDir(cacheRoot)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		slog.Warn("pluginskills: could not read plugin cache dir; skipping", "path", cacheRoot, "err", err)
		return nil, nil
	}

	for _, mktEntry := range marketplaces {
		if !mktEntry.IsDir() {
			continue
		}
		marketplaceDir := filepath.Join(cacheRoot, mktEntry.Name())

		// Enumerate plugins within this marketplace.
		plugins, err := os.ReadDir(marketplaceDir)
		if err != nil {
			slog.Warn("pluginskills: could not read marketplace dir; skipping",
				"marketplace", mktEntry.Name(), "err", err)
			continue
		}

		for _, pluginEntry := range plugins {
			if !pluginEntry.IsDir() {
				continue
			}
			pluginName := pluginEntry.Name()
			skillsDir := filepath.Join(marketplaceDir, pluginName, "skills")

			skillEntries, err := os.ReadDir(skillsDir)
			if err != nil {
				if !os.IsNotExist(err) {
					slog.Warn("pluginskills: could not read skills dir; skipping",
						"plugin", pluginName, "err", err)
				}
				continue
			}

			for _, skillEntry := range skillEntries {
				if !skillEntry.IsDir() {
					continue
				}
				skillName := skillEntry.Name()
				skillFile := filepath.Join(skillsDir, skillName, "SKILL.md")
				if _, statErr := os.Stat(skillFile); statErr != nil {
					// No SKILL.md — skip silently.
					continue
				}
				handle := pluginName + ":" + skillName
				pn := pluginName
				skills = append(skills, command.SkillManifestEntry{
					Name:       handle,
					Source:     "plugin",
					PluginName: &pn,
				})
			}
		}
	}
	return skills, nil
}
