// Startup reconciliation — when the supervisor restarts and finds
// workspace directories left over from a previous run (process crash,
// pod replace, OOM-kill), it can't know which backend workflow they
// belong to from the directory alone. The cheapest reliable signal:
// every CreateWorkspace writes a `.workspace-id` manifest file into the
// tempdir as the workspace_id; on startup the supervisor scans the
// workspace root, reads each manifest, and reports the resulting
// workspace_ids in its first heartbeat with `status="unknown"`. The
// backend can then either reclaim them (if the originating workflow is
// still live) or signal cleanup via the heartbeat response's
// `forgotten_workspaces` list (forwarded handling lands in the
// disk-janitor slice).
//
// No directory-name parsing here — manifest files survive across
// `os.MkdirTemp` implementation changes and are language-agnostic.

package supervisor

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/yaaos/agent/internal/protocol"
)

// WorkspaceManifestName is the filename the workspace handler writes
// inside each tempdir containing the workspace_id. Read on startup so
// orphan dirs can be reattributed without parsing dir names.
const WorkspaceManifestName = ".workspace-id"

// scanOrphanWorkspaces walks `root` one level deep, looks for
// `<dir>/.workspace-id` manifest files, and returns a heartbeat-entry
// list for each. Missing root / unreadable directory entries are
// logged + skipped — startup reconciliation is best-effort by design.
func scanOrphanWorkspaces(root string, log Logger) []protocol.HeartbeatWorkspaceEntry {
	if root == "" {
		return nil
	}
	if log == nil {
		log = nullLogger{}
	}
	entries, err := os.ReadDir(root)
	if err != nil {
		// Missing root is normal on a fresh pod; log at info, not warn.
		if os.IsNotExist(err) {
			log.Info("reconcile.scan_skipped", "reason", "root_missing", "root", root)
			return nil
		}
		log.Warn("reconcile.scan_failed", "root", root, "err", err.Error())
		return nil
	}
	var out []protocol.HeartbeatWorkspaceEntry
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		manifestPath := filepath.Join(root, e.Name(), WorkspaceManifestName)
		raw, err := os.ReadFile(manifestPath)
		if err != nil {
			// Not every dir under root has to be a workspace; missing
			// manifest = silent skip. Other read errors → warn.
			if !os.IsNotExist(err) {
				log.Warn("reconcile.manifest_read_failed",
					"path", manifestPath, "err", err.Error())
			}
			continue
		}
		id := strings.TrimSpace(string(raw))
		if id == "" {
			log.Warn("reconcile.empty_manifest", "path", manifestPath)
			continue
		}
		out = append(out, protocol.HeartbeatWorkspaceEntry{
			WorkspaceID: id,
			Status:      "unknown",
		})
		log.Info("reconcile.orphan_found", "workspace_id", id, "path", filepath.Join(root, e.Name()))
	}
	return out
}
