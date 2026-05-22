package workspace

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/yaaos/agent/internal/protocol"
)

func newCreate(workspaceID string) *protocol.CreateWorkspaceCommand {
	return &protocol.CreateWorkspaceCommand{
		CommandHeader: protocol.CommandHeader{
			CommandID:   "c-create-" + workspaceID,
			WorkspaceID: workspaceID,
			Kind:        protocol.KindCreateWorkspace,
		},
		Repo: protocol.RepoRef{
			PluginID:   "github",
			ExternalID: "acme/web",
			CloneURL:   "https://github.com/acme/web.git",
			HeadSHA:    "deadbeef",
		},
		Auth: protocol.AuthBlock{Kind: "github_installation", Token: "tok-abc"},
	}
}

func TestRealHandler_CreateWorkspace_AllocatesTempDir(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	out, err := h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	path, _ := out["path"].(string)
	if path == "" {
		t.Fatal("output missing path")
	}
	if _, err := os.Stat(path); err != nil {
		t.Errorf("tempdir not created: %v", err)
	}
	if out["clone_pending"] != true {
		t.Errorf("want clone_pending=true, got %v", out["clone_pending"])
	}
	if out["repo"] != "acme/web" {
		t.Errorf("repo: want acme/web got %v", out["repo"])
	}
}

func TestRealHandler_CreateWorkspace_IdempotentOnSecondCall(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	out1, err := h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	if err != nil {
		t.Fatalf("create #1: %v", err)
	}
	out2, err := h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	if err != nil {
		t.Fatalf("create #2: %v", err)
	}
	if out2["path"] != out1["path"] {
		t.Errorf("second create should reuse path %q, got %q", out1["path"], out2["path"])
	}
	if out2["reused"] != true {
		t.Errorf("second create should report reused=true")
	}
}

func TestRealHandler_WriteFiles_WritesEntries(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	out, _ := h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	wsPath := out["path"].(string)

	files := []protocol.WriteFilesEntry{
		{Path: ".mcp.json", Content: `{"servers":[]}`},
		{Path: "src/foo.py", Content: "print('hi')\n"},
	}
	res, err := h.WriteFiles(context.Background(), &protocol.WriteFilesCommand{
		CommandHeader: protocol.CommandHeader{
			CommandID: "c-write", WorkspaceID: "ws-1", Kind: protocol.KindWriteFiles,
		},
		Files: files,
	})
	if err != nil {
		t.Fatalf("write: %v", err)
	}
	if got := res["files_count"]; got != 2 {
		t.Errorf("files_count: want 2 got %v", got)
	}
	for _, f := range files {
		path := filepath.Join(wsPath, f.Path)
		got, err := os.ReadFile(path)
		if err != nil {
			t.Errorf("read %s: %v", path, err)
			continue
		}
		if string(got) != f.Content {
			t.Errorf("file %s: want %q got %q", f.Path, f.Content, string(got))
		}
	}
}

func TestRealHandler_WriteFiles_UnknownWorkspace_Errors(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	_, err := h.WriteFiles(context.Background(), &protocol.WriteFilesCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c", WorkspaceID: "missing"},
		Files:         []protocol.WriteFilesEntry{{Path: "f", Content: "x"}},
	})
	if !errors.Is(err, ErrUnknownWorkspace) {
		t.Errorf("want ErrUnknownWorkspace, got %v", err)
	}
}

func TestRealHandler_WriteFiles_RejectsPathEscape(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	h.CreateWorkspace(context.Background(), newCreate("ws-1"))

	cases := []string{
		"../escape.txt",
		"/etc/passwd",
		"a/../../b",
		"",
	}
	for _, p := range cases {
		_, err := h.WriteFiles(context.Background(), &protocol.WriteFilesCommand{
			CommandHeader: protocol.CommandHeader{CommandID: "c", WorkspaceID: "ws-1"},
			Files:         []protocol.WriteFilesEntry{{Path: p, Content: "x"}},
		})
		if err == nil {
			t.Errorf("path %q should be rejected", p)
		}
	}
}

func TestRealHandler_RefreshWorkspaceAuth_UpdatesToken(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	if h.slots["ws-1"].authTok != "tok-abc" {
		t.Fatalf("initial token wrong: %q", h.slots["ws-1"].authTok)
	}

	_, err := h.RefreshWorkspaceAuth(context.Background(), &protocol.RefreshWorkspaceAuthCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c-refresh", WorkspaceID: "ws-1"},
		NewToken:      "tok-xyz",
	})
	if err != nil {
		t.Fatalf("refresh: %v", err)
	}
	if got := h.slots["ws-1"].authTok; got != "tok-xyz" {
		t.Errorf("token after refresh: want tok-xyz got %q", got)
	}
}

func TestRealHandler_RefreshWorkspaceAuth_UnknownWorkspace_Errors(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	_, err := h.RefreshWorkspaceAuth(context.Background(), &protocol.RefreshWorkspaceAuthCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c", WorkspaceID: "missing"},
		NewToken:      "x",
	})
	if !errors.Is(err, ErrUnknownWorkspace) {
		t.Errorf("want ErrUnknownWorkspace, got %v", err)
	}
}

func TestRealHandler_CleanupWorkspace_RemovesTempDirAndSlot(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	out, _ := h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	wsPath := out["path"].(string)

	res, err := h.CleanupWorkspace(context.Background(), &protocol.CleanupWorkspaceCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c-clean", WorkspaceID: "ws-1"},
	})
	if err != nil {
		t.Fatalf("cleanup: %v", err)
	}
	if res["destroyed"] != true {
		t.Errorf("want destroyed=true, got %v", res["destroyed"])
	}
	if _, err := os.Stat(wsPath); !os.IsNotExist(err) {
		t.Errorf("tempdir still present: %v", err)
	}
	if _, ok := h.slots["ws-1"]; ok {
		t.Errorf("slot not dropped")
	}
}

func TestRealHandler_CleanupWorkspace_UnknownWorkspace_IdempotentSuccess(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	res, err := h.CleanupWorkspace(context.Background(), &protocol.CleanupWorkspaceCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c", WorkspaceID: "ghost"},
	})
	if err != nil {
		t.Fatalf("cleanup of unknown should succeed, got %v", err)
	}
	if res["destroyed"] != false {
		t.Errorf("destroyed: want false got %v", res["destroyed"])
	}
}

func TestRealHandler_InvokeClaudeCode_NotImplemented(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	_, err := h.InvokeClaudeCode(context.Background(), &protocol.InvokeClaudeCodeCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c-inv", WorkspaceID: "ws-1"},
	})
	if err == nil {
		t.Fatal("want explicit not-implemented error")
	}
	if !strings.Contains(err.Error(), "not yet implemented") {
		t.Errorf("err: want 'not yet implemented' substring, got %q", err.Error())
	}
}

func TestRealHandler_InvokeClaudeCode_UnknownWorkspace_Errors(t *testing.T) {
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	_, err := h.InvokeClaudeCode(context.Background(), &protocol.InvokeClaudeCodeCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c", WorkspaceID: "missing"},
	})
	if !errors.Is(err, ErrUnknownWorkspace) {
		t.Errorf("want ErrUnknownWorkspace, got %v", err)
	}
}

func TestRealHandler_FullLifecycle_CreateWriteCleanup(t *testing.T) {
	// End-to-end: drive a fresh workspace through Create → WriteFiles →
	// Cleanup and assert the file lands then disappears.
	h := NewRealHandler(RealHandlerConfig{Root: t.TempDir()})
	cr, _ := h.CreateWorkspace(context.Background(), newCreate("ws-1"))
	wsPath := cr["path"].(string)
	h.WriteFiles(context.Background(), &protocol.WriteFilesCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c-w", WorkspaceID: "ws-1"},
		Files:         []protocol.WriteFilesEntry{{Path: "hello.txt", Content: "world"}},
	})
	if _, err := os.Stat(filepath.Join(wsPath, "hello.txt")); err != nil {
		t.Fatalf("file before cleanup: %v", err)
	}
	h.CleanupWorkspace(context.Background(), &protocol.CleanupWorkspaceCommand{
		CommandHeader: protocol.CommandHeader{CommandID: "c-clean", WorkspaceID: "ws-1"},
	})
	if _, err := os.Stat(wsPath); !os.IsNotExist(err) {
		t.Errorf("workspace tree should be gone after cleanup, got %v", err)
	}
}

func TestSafeJoin(t *testing.T) {
	base := "/ws"
	cases := []struct {
		rel   string
		ok    bool
		want  string
	}{
		{"a.txt", true, "/ws/a.txt"},
		{"src/foo.py", true, "/ws/src/foo.py"},
		{"./x", true, "/ws/x"},
		{"../escape", false, ""},
		{"/etc/passwd", false, ""},
		{"a/../../b", false, ""},
		{"", false, ""},
	}
	for _, c := range cases {
		got, err := safeJoin(base, c.rel)
		if c.ok && err != nil {
			t.Errorf("safeJoin(%q): want ok, got err=%v", c.rel, err)
		}
		if !c.ok && err == nil {
			t.Errorf("safeJoin(%q): want err, got %q", c.rel, got)
		}
		if c.ok && got != c.want {
			t.Errorf("safeJoin(%q): want %q got %q", c.rel, c.want, got)
		}
	}
}

func TestSanitizeID(t *testing.T) {
	cases := []struct{ in, want string }{
		{"abc-123", "abc-123"},
		{"abc/../etc", "abcetc"},
		{"", "anon"},
		{strings.Repeat("a", 100), strings.Repeat("a", 32)},
	}
	for _, c := range cases {
		if got := sanitizeID(c.in); got != c.want {
			t.Errorf("sanitizeID(%q): want %q got %q", c.in, c.want, got)
		}
	}
}
