// pluginskills_test.go — unit tests for the plugin/marketplace skill installer.
//
// Subprocess invocations are faked at the `pluginRunner` package seam — no
// real `claude` binary is exec'd. Cache scans run against a fake HOME assembled
// per-test with t.TempDir().

package workspace

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/yaaos/agent/internal/command"
)

// --- parseClaudeSettings ---

func TestParseClaudeSettings_MissingFile(t *testing.T) {
	t.Helper()
	dir := t.TempDir()
	got, err := parseClaudeSettings(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got.ExtraKnownMarketplaces) != 0 || len(got.EnabledPlugins) != 0 {
		t.Fatalf("expected empty struct on missing file, got %+v", got)
	}
}

func TestParseClaudeSettings_Malformed(t *testing.T) {
	t.Helper()
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, ".claude"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, ".claude", "settings.json"), []byte("not json"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	got, err := parseClaudeSettings(dir)
	if err != nil {
		t.Fatalf("malformed settings.json should degrade gracefully, got err: %v", err)
	}
	if len(got.ExtraKnownMarketplaces) != 0 || len(got.EnabledPlugins) != 0 {
		t.Fatalf("expected empty struct on malformed JSON, got %+v", got)
	}
}

func TestParseClaudeSettings_Valid(t *testing.T) {
	t.Helper()
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, ".claude"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := `{
		"extraKnownMarketplaces": ["https://example.com/mkt"],
		"enabledPlugins": ["foo@example", "bar@example"]
	}`
	if err := os.WriteFile(filepath.Join(dir, ".claude", "settings.json"), []byte(body), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	got, err := parseClaudeSettings(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got.ExtraKnownMarketplaces) != 1 || got.ExtraKnownMarketplaces[0] != "https://example.com/mkt" {
		t.Fatalf("marketplaces: %+v", got.ExtraKnownMarketplaces)
	}
	if len(got.EnabledPlugins) != 2 || got.EnabledPlugins[0] != "foo@example" {
		t.Fatalf("plugins: %+v", got.EnabledPlugins)
	}
}

// --- InstallPluginSkills ---

// withFakeRunner replaces pluginRunner for the lifetime of the test, recording
// each call's argv. Restoration is registered with t.Cleanup.
func withFakeRunner(t *testing.T, runner func(ctx context.Context, cwd string, args ...string) error) *[][]string {
	t.Helper()
	calls := &[][]string{}
	prev := pluginRunner
	pluginRunner = func(ctx context.Context, cwd string, args ...string) error {
		*calls = append(*calls, append([]string{cwd}, args...))
		return runner(ctx, cwd, args...)
	}
	t.Cleanup(func() { pluginRunner = prev })
	return calls
}

// withFakeHome points HOME at t.TempDir() and seeds an empty plugin cache so
// scanPluginCacheSkills returns deterministic results. Returns the cache root.
func withFakeHome(t *testing.T) string {
	t.Helper()
	home := t.TempDir()
	t.Setenv("HOME", home)
	cacheDir := filepath.Join(home, ".claude", "plugins", "cache")
	if err := os.MkdirAll(cacheDir, 0o755); err != nil {
		t.Fatalf("mkdir cache: %v", err)
	}
	return cacheDir
}

func TestInstallPluginSkills_NoSettings_NoCalls(t *testing.T) {
	dir := t.TempDir()
	calls := withFakeRunner(t, func(_ context.Context, _ string, _ ...string) error { return nil })
	_ = withFakeHome(t)
	got, err := InstallPluginSkills(context.Background(), dir, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != nil {
		t.Fatalf("expected nil skills on empty settings, got %+v", got)
	}
	if len(*calls) != 0 {
		t.Fatalf("expected zero subprocess calls, got %d: %+v", len(*calls), *calls)
	}
}

func TestInstallPluginSkills_MarketplaceThenInstall_InvocationOrder(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, ".claude"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := `{
		"extraKnownMarketplaces": ["mkt-a", "mkt-b"],
		"enabledPlugins": ["plug-1@mkt-a", "plug-2@mkt-b"]
	}`
	if err := os.WriteFile(filepath.Join(dir, ".claude", "settings.json"), []byte(body), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	calls := withFakeRunner(t, func(_ context.Context, _ string, _ ...string) error { return nil })
	_ = withFakeHome(t)

	if _, err := InstallPluginSkills(context.Background(), dir, ""); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(*calls) != 4 {
		t.Fatalf("expected 4 calls (2 marketplace add + 2 install), got %d: %+v", len(*calls), *calls)
	}
	// Marketplace adds come before plugin installs.
	expect := [][]string{
		{dir, "marketplace", "add", "mkt-a"},
		{dir, "marketplace", "add", "mkt-b"},
		{dir, "install", "plug-1@mkt-a"},
		{dir, "install", "plug-2@mkt-b"},
	}
	for i, want := range expect {
		got := (*calls)[i]
		if len(got) != len(want) {
			t.Fatalf("call %d arity mismatch: got %v, want %v", i, got, want)
		}
		for j := range want {
			if got[j] != want[j] {
				t.Fatalf("call %d arg %d: got %q, want %q (full call %v)", i, j, got[j], want[j], got)
			}
		}
	}
}

func TestInstallPluginSkills_GracefulDegrade_OneFailingPluginDoesNotAbort(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, ".claude"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := `{"enabledPlugins": ["bad@mkt", "good@mkt"]}`
	if err := os.WriteFile(filepath.Join(dir, ".claude", "settings.json"), []byte(body), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	calls := withFakeRunner(t, func(_ context.Context, _ string, args ...string) error {
		// Fail the install of "bad@mkt"; succeed for "good@mkt".
		if len(args) >= 2 && args[0] == "install" && args[1] == "bad@mkt" {
			return errors.New("simulated install failure")
		}
		return nil
	})
	_ = withFakeHome(t)

	// Should not propagate the per-plugin error; install of "good@mkt" still runs.
	if _, err := InstallPluginSkills(context.Background(), dir, ""); err != nil {
		t.Fatalf("expected graceful degrade (no error), got: %v", err)
	}
	if len(*calls) != 2 {
		t.Fatalf("expected 2 install attempts (both plugins, despite one failing), got %d: %+v", len(*calls), *calls)
	}
}

// --- scanPluginCacheSkills ---

func TestScanPluginCacheSkills_EmitsNamespacedHandles(t *testing.T) {
	cacheDir := withFakeHome(t)
	// Lay out cache/<marketplace>/<plugin>/skills/<skill>/SKILL.md
	mustWrite := func(p string) {
		t.Helper()
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatalf("mkdir: %v", err)
		}
		if err := os.WriteFile(p, []byte("# skill\n"), 0o644); err != nil {
			t.Fatalf("write: %v", err)
		}
	}
	mustWrite(filepath.Join(cacheDir, "mkt-a", "plug-1", "skills", "alpha", "SKILL.md"))
	mustWrite(filepath.Join(cacheDir, "mkt-a", "plug-1", "skills", "beta", "SKILL.md"))
	mustWrite(filepath.Join(cacheDir, "mkt-b", "plug-2", "skills", "gamma", "SKILL.md"))
	// A skill directory without SKILL.md is silently skipped.
	if err := os.MkdirAll(filepath.Join(cacheDir, "mkt-b", "plug-2", "skills", "no-skill-md"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	got, err := scanPluginCacheSkills()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := map[string]string{
		"plug-1:alpha": "plug-1",
		"plug-1:beta":  "plug-1",
		"plug-2:gamma": "plug-2",
	}
	if len(got) != len(want) {
		t.Fatalf("expected %d entries, got %d: %+v", len(want), len(got), got)
	}
	for _, e := range got {
		if e.Source != "plugin" {
			t.Errorf("entry %s: source = %q, want plugin", e.Name, e.Source)
		}
		if e.PluginName == nil {
			t.Errorf("entry %s: PluginName nil, want non-nil", e.Name)
			continue
		}
		wantPlugin, ok := want[e.Name]
		if !ok {
			t.Errorf("unexpected entry %s", e.Name)
			continue
		}
		if *e.PluginName != wantPlugin {
			t.Errorf("entry %s: plugin_name = %q, want %q", e.Name, *e.PluginName, wantPlugin)
		}
	}
}

func TestScanPluginCacheSkills_NoCache_ReturnsEmpty(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	// No ~/.claude/plugins/cache created.
	got, err := scanPluginCacheSkills()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("expected empty list when cache absent, got %+v", got)
	}
}

// --- end-to-end: settings → install → scan, all wired through the seam ---

func TestInstallPluginSkills_EndToEnd_PopulatesCacheAndReturnsManifest(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, ".claude"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := `{"enabledPlugins": ["plug-x@mkt"]}`
	if err := os.WriteFile(filepath.Join(dir, ".claude", "settings.json"), []byte(body), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	cacheDir := withFakeHome(t)

	// Fake runner: simulate `claude plugin install plug-x@mkt` populating the
	// plugin cache as the real CLI would.
	_ = withFakeRunner(t, func(_ context.Context, _ string, args ...string) error {
		if len(args) >= 2 && args[0] == "install" && args[1] == "plug-x@mkt" {
			skillPath := filepath.Join(cacheDir, "mkt", "plug-x", "skills", "review", "SKILL.md")
			if err := os.MkdirAll(filepath.Dir(skillPath), 0o755); err != nil {
				return err
			}
			return os.WriteFile(skillPath, []byte("# skill\n"), 0o644)
		}
		return nil
	})

	got, err := InstallPluginSkills(context.Background(), dir, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("expected 1 skill in manifest, got %d: %+v", len(got), got)
	}
	want := command.SkillManifestEntry{Name: "plug-x:review", Source: "plugin"}
	if got[0].Name != want.Name || got[0].Source != want.Source {
		t.Errorf("entry: got %+v, want %+v", got[0], want)
	}
	if got[0].PluginName == nil || *got[0].PluginName != "plug-x" {
		t.Errorf("plugin_name: got %v, want plug-x", got[0].PluginName)
	}
}
