package supervisor

import (
	"os"
	"path/filepath"
	"sort"
	"testing"
)

// plantWorkspace mimics what `workspace.RealHandler.CreateWorkspace` does
// on disk: an `os.MkdirTemp`-style tempdir with a `.workspace-id`
// manifest file at the top.
func plantWorkspace(t *testing.T, root, workspaceID string) string {
	t.Helper()
	dir, err := os.MkdirTemp(root, "yaaos-ws-")
	if err != nil {
		t.Fatalf("plant: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, WorkspaceManifestName), []byte(workspaceID), 0o600); err != nil {
		t.Fatalf("plant manifest: %v", err)
	}
	return dir
}

func TestScanOrphanWorkspaces_FindsPlantedDirs(t *testing.T) {
	root := t.TempDir()
	plantWorkspace(t, root, "ws-a")
	plantWorkspace(t, root, "ws-b")
	plantWorkspace(t, root, "ws-c")

	got := scanOrphanWorkspaces(root, nil)
	ids := make([]string, len(got))
	for i, e := range got {
		ids[i] = e.WorkspaceID
		if e.Status != "unknown" {
			t.Errorf("status: want unknown, got %q", e.Status)
		}
	}
	sort.Strings(ids)
	want := []string{"ws-a", "ws-b", "ws-c"}
	if len(ids) != 3 {
		t.Fatalf("want 3 entries, got %d: %v", len(ids), ids)
	}
	for i := range want {
		if ids[i] != want[i] {
			t.Errorf("orphan %d: want %s got %s", i, want[i], ids[i])
		}
	}
}

func TestScanOrphanWorkspaces_EmptyRootReturnsNil(t *testing.T) {
	root := t.TempDir()
	if got := scanOrphanWorkspaces(root, nil); len(got) != 0 {
		t.Errorf("want no orphans in empty root, got %v", got)
	}
}

func TestScanOrphanWorkspaces_MissingRootIsOK(t *testing.T) {
	if got := scanOrphanWorkspaces("/does/not/exist/yaaos", nil); len(got) != 0 {
		t.Errorf("missing root should return nil, got %v", got)
	}
}

func TestScanOrphanWorkspaces_EmptyRootStringSkips(t *testing.T) {
	if got := scanOrphanWorkspaces("", nil); got != nil {
		t.Errorf("empty root should skip, got %v", got)
	}
}

func TestScanOrphanWorkspaces_SkipsDirsWithoutManifest(t *testing.T) {
	root := t.TempDir()
	// Real workspace.
	plantWorkspace(t, root, "ws-real")
	// Unrelated dir — no manifest. Should be skipped silently.
	unrelated := filepath.Join(root, "not-a-workspace")
	_ = os.Mkdir(unrelated, 0o755)
	// File at root level (not a dir) — also skipped.
	_ = os.WriteFile(filepath.Join(root, "stray.log"), []byte("x"), 0o600)

	got := scanOrphanWorkspaces(root, nil)
	if len(got) != 1 || got[0].WorkspaceID != "ws-real" {
		t.Errorf("want only ws-real, got %v", got)
	}
}

func TestScanOrphanWorkspaces_SkipsEmptyManifest(t *testing.T) {
	root := t.TempDir()
	dir, _ := os.MkdirTemp(root, "yaaos-ws-")
	_ = os.WriteFile(filepath.Join(dir, WorkspaceManifestName), []byte("   \n"), 0o600)

	got := scanOrphanWorkspaces(root, nil)
	if len(got) != 0 {
		t.Errorf("empty manifest should be skipped, got %v", got)
	}
}

func TestScanOrphanWorkspaces_TrimsWhitespace(t *testing.T) {
	root := t.TempDir()
	dir, _ := os.MkdirTemp(root, "yaaos-ws-")
	_ = os.WriteFile(filepath.Join(dir, WorkspaceManifestName), []byte("\n  ws-trim  \n"), 0o600)

	got := scanOrphanWorkspaces(root, nil)
	if len(got) != 1 || got[0].WorkspaceID != "ws-trim" {
		t.Errorf("want ws-trim, got %v", got)
	}
}
