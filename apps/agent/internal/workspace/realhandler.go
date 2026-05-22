// RealHandler — production workspace.Handler that owns the per-workspace
// tempdir lifecycle. Implements four of five AgentCommand kinds:
//
//   - CreateWorkspace      — `os.MkdirTemp` under the configured root,
//                            stash auth + repo metadata in an in-memory
//                            slot keyed by workspace_id. Git clone is
//                            deferred to a follow-on (it'd need either
//                            the `git` binary in the runtime image or a
//                            pure-Go go-git dep). Emits a structured
//                            `clone_pending=true` output so the backend
//                            can observe the deferral.
//   - WriteFiles           — write each (path, content) entry under the
//                            workspace root. Refuses paths that escape
//                            the root via `..` or absolute components.
//   - RefreshWorkspaceAuth — overwrite the stored auth token in-place.
//                            No I/O — used by the supervisor when the
//                            backend rotates a GitHub installation token
//                            mid-flight.
//   - CleanupWorkspace     — `os.RemoveAll` the tempdir + drop the slot.
//                            Idempotent on a missing workspace_id.
//
// InvokeClaudeCode stays a `not yet implemented` error in this slice —
// it lands when the Claude Code subprocess wrapper is wired (per slice
// 65's TODO note + DECISIONS.md).
//
// Concurrency: a single sync.Mutex serializes slot lookups + mutations.
// Each Handler method is short and non-blocking; the workspace process
// itself dispatches commands single-file via `workspace.Run`, so
// contention is bounded by the supervisor's per-workspace pool serializer.

package workspace

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/yaaos/agent/internal/protocol"
)

// RealHandlerConfig customizes the production handler's behaviour. Zero
// values pick safe defaults.
type RealHandlerConfig struct {
	// Root is the parent directory that holds per-workspace tempdirs.
	// Empty string means `os.TempDir()`. Production deployments mount a
	// dedicated EBS volume here so disk failures don't take the agent
	// process down.
	Root string

	// DirPerm is the permission bits applied to the per-workspace
	// tempdir + every directory we mkdir inside it. Defaults to 0o700 —
	// the workspace contents are customer source code; no other Linux
	// user on the host can read them.
	DirPerm os.FileMode

	// FilePerm is the permission bits applied to files written via
	// WriteFiles. Defaults to 0o600.
	FilePerm os.FileMode
}

// realSlot tracks one workspace's state across the command sequence.
type realSlot struct {
	path     string // absolute filesystem path of the workspace tempdir
	repo     protocol.RepoRef
	authKind string // "github_installation" | "oauth"
	authTok  string // raw token; never logged
}

// RealHandler implements workspace.Handler for production. Construct
// with NewRealHandler.
type RealHandler struct {
	cfg     RealHandlerConfig
	mu      sync.Mutex
	slots   map[string]*realSlot
}

// NewRealHandler returns a fresh handler with the given config. Use
// `workspace.Run(ctx, in, out, NewRealHandler(...), opts)` from the
// `agent workspace` subcommand entry.
func NewRealHandler(cfg RealHandlerConfig) *RealHandler {
	if cfg.DirPerm == 0 {
		cfg.DirPerm = 0o700
	}
	if cfg.FilePerm == 0 {
		cfg.FilePerm = 0o600
	}
	return &RealHandler{cfg: cfg, slots: make(map[string]*realSlot)}
}

// ErrUnknownWorkspace is returned by WriteFiles / RefreshWorkspaceAuth /
// InvokeClaudeCode when no CreateWorkspace has run for the given
// workspace_id. The supervisor surfaces this as a completed_failure
// event; the backend's workflow engine treats it as a fatal step error.
var ErrUnknownWorkspace = errors.New("workspace not created")

func (h *RealHandler) CreateWorkspace(_ context.Context, cmd *protocol.CreateWorkspaceCommand) (map[string]any, error) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if _, exists := h.slots[cmd.WorkspaceID]; exists {
		// Idempotent: a second CreateWorkspace for the same id is a
		// supervisor-side bug, but we don't want to crash the workspace
		// process — log via the output and keep the existing slot.
		slot := h.slots[cmd.WorkspaceID]
		return map[string]any{
			"workspace_id": cmd.WorkspaceID,
			"path":         slot.path,
			"reused":       true,
			"clone_pending": true,
		}, nil
	}
	root := h.cfg.Root
	if root == "" {
		root = os.TempDir()
	}
	path, err := os.MkdirTemp(root, "yaaos-ws-"+sanitizeID(cmd.WorkspaceID)+"-")
	if err != nil {
		return nil, fmt.Errorf("mkdir tempdir: %w", err)
	}
	if err := os.Chmod(path, h.cfg.DirPerm); err != nil {
		// Best-effort: the tempdir already exists with default perms.
		// Don't fail the command on chmod.
		_ = err
	}
	h.slots[cmd.WorkspaceID] = &realSlot{
		path:     path,
		repo:     cmd.Repo,
		authKind: cmd.Auth.Kind,
		authTok:  cmd.Auth.Token,
	}
	// Git clone is deferred to a follow-on. The workspace tempdir
	// exists; downstream WriteFiles/InvokeClaudeCode work but operate
	// on an empty tree until clone lands.
	return map[string]any{
		"workspace_id":  cmd.WorkspaceID,
		"path":          path,
		"clone_pending": true,
		"repo":          cmd.Repo.ExternalID,
		"head_sha":      cmd.Repo.HeadSHA,
	}, nil
}

func (h *RealHandler) WriteFiles(_ context.Context, cmd *protocol.WriteFilesCommand) (map[string]any, error) {
	h.mu.Lock()
	slot, ok := h.slots[cmd.WorkspaceID]
	h.mu.Unlock()
	if !ok {
		return nil, ErrUnknownWorkspace
	}
	written := 0
	for _, entry := range cmd.Files {
		full, err := safeJoin(slot.path, entry.Path)
		if err != nil {
			return nil, fmt.Errorf("file %q: %w", entry.Path, err)
		}
		if err := os.MkdirAll(filepath.Dir(full), h.cfg.DirPerm); err != nil {
			return nil, fmt.Errorf("file %q: mkdir parent: %w", entry.Path, err)
		}
		if err := os.WriteFile(full, []byte(entry.Content), h.cfg.FilePerm); err != nil {
			return nil, fmt.Errorf("file %q: write: %w", entry.Path, err)
		}
		written++
	}
	return map[string]any{
		"workspace_id": cmd.WorkspaceID,
		"files_count":  written,
	}, nil
}

func (h *RealHandler) RefreshWorkspaceAuth(_ context.Context, cmd *protocol.RefreshWorkspaceAuthCommand) (map[string]any, error) {
	h.mu.Lock()
	defer h.mu.Unlock()
	slot, ok := h.slots[cmd.WorkspaceID]
	if !ok {
		return nil, ErrUnknownWorkspace
	}
	slot.authTok = cmd.NewToken
	return map[string]any{
		"workspace_id": cmd.WorkspaceID,
		"refreshed":    true,
	}, nil
}

func (h *RealHandler) InvokeClaudeCode(_ context.Context, cmd *protocol.InvokeClaudeCodeCommand) (map[string]any, error) {
	h.mu.Lock()
	_, ok := h.slots[cmd.WorkspaceID]
	h.mu.Unlock()
	if !ok {
		return nil, ErrUnknownWorkspace
	}
	// Real Claude Code subprocess wiring lands in a follow-on slice.
	// Returning an explicit error here surfaces the gap to the backend's
	// workflow engine rather than silently completing the step.
	return nil, errors.New("InvokeClaudeCode: subprocess wiring not yet implemented (Phase 6 follow-on)")
}

func (h *RealHandler) CleanupWorkspace(_ context.Context, cmd *protocol.CleanupWorkspaceCommand) (map[string]any, error) {
	h.mu.Lock()
	slot, ok := h.slots[cmd.WorkspaceID]
	if ok {
		delete(h.slots, cmd.WorkspaceID)
	}
	h.mu.Unlock()
	if !ok {
		// Idempotent: cleanup of an unknown workspace is a no-op success.
		return map[string]any{
			"workspace_id": cmd.WorkspaceID,
			"destroyed":    false,
			"reason":       "unknown_workspace",
		}, nil
	}
	if err := os.RemoveAll(slot.path); err != nil {
		return nil, fmt.Errorf("cleanup %q: %w", slot.path, err)
	}
	return map[string]any{
		"workspace_id": cmd.WorkspaceID,
		"destroyed":    true,
		"path":         slot.path,
	}, nil
}

// safeJoin guards against path-escape attacks. The supplied `rel` must
// not start with `/`, must not contain `..` segments, and must resolve
// (after Clean) to a subpath of `base`.
func safeJoin(base, rel string) (string, error) {
	if rel == "" {
		return "", errors.New("empty path")
	}
	if filepath.IsAbs(rel) {
		return "", errors.New("absolute path not allowed")
	}
	cleaned := filepath.Clean(rel)
	if strings.HasPrefix(cleaned, "..") || strings.Contains(cleaned, string(filepath.Separator)+"..") {
		return "", errors.New("parent-directory traversal not allowed")
	}
	full := filepath.Join(base, cleaned)
	// Double-check via Rel — defence in depth against any os-specific
	// quirk in Clean/Join.
	rel2, err := filepath.Rel(base, full)
	if err != nil || strings.HasPrefix(rel2, "..") {
		return "", errors.New("path escapes workspace root")
	}
	return full, nil
}

// sanitizeID strips characters that aren't safe in a filesystem name.
// We expect UUIDs here (alnum + dashes), so we just filter to that set.
func sanitizeID(id string) string {
	out := make([]byte, 0, len(id))
	for i := 0; i < len(id); i++ {
		c := id[i]
		switch {
		case c >= '0' && c <= '9', c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c == '-', c == '_':
			out = append(out, c)
		}
	}
	if len(out) == 0 {
		return "anon"
	}
	if len(out) > 32 {
		out = out[:32]
	}
	return string(out)
}
