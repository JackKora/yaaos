package supervisor

import (
	"context"
	"errors"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/yaaos/agent/internal/protocol"
	"github.com/yaaos/agent/internal/workspace"
)

func newCreateCmd(workspaceID, commandID string) *protocol.AgentCommand {
	return &protocol.AgentCommand{
		Kind: protocol.KindCreateWorkspace,
		CreateWorkspace: &protocol.CreateWorkspaceCommand{
			CommandHeader: protocol.CommandHeader{
				CommandID:   commandID,
				WorkspaceID: workspaceID,
				Traceparent: "tp-" + commandID,
				Kind:        protocol.KindCreateWorkspace,
			},
		},
	}
}

func newWriteCmd(workspaceID, commandID string) *protocol.AgentCommand {
	return &protocol.AgentCommand{
		Kind: protocol.KindWriteFiles,
		WriteFiles: &protocol.WriteFilesCommand{
			CommandHeader: protocol.CommandHeader{
				CommandID: commandID, WorkspaceID: workspaceID, Traceparent: "tp-" + commandID,
				Kind: protocol.KindWriteFiles,
			},
		},
	}
}

func newCleanupCmd(workspaceID, commandID string) *protocol.AgentCommand {
	return &protocol.AgentCommand{
		Kind: protocol.KindCleanupWorkspace,
		CleanupWorkspace: &protocol.CleanupWorkspaceCommand{
			CommandHeader: protocol.CommandHeader{
				CommandID: commandID, WorkspaceID: workspaceID, Traceparent: "tp-" + commandID,
				Kind: protocol.KindCleanupWorkspace,
			},
		},
	}
}

func TestPool_FirstCommandSpawnsRunner_SuccessEvent(t *testing.T) {
	pool := NewPool(InProcessSpawn(workspace.StubHandler{}), nil)
	defer pool.CloseAll(context.Background())

	ev := pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-1"))
	if ev.Kind != protocol.EventCompletedSuccess {
		t.Fatalf("kind: want completed_success got %q (reason=%q)", ev.Kind, ev.FailureReason)
	}
	if ev.CommandID != "c-1" {
		t.Errorf("command_id: want c-1 got %q", ev.CommandID)
	}
	if ev.Traceparent != "tp-c-1" {
		t.Errorf("traceparent: want tp-c-1 got %q", ev.Traceparent)
	}
}

func TestPool_NonCreateForUnknownWorkspace_Failure(t *testing.T) {
	pool := NewPool(InProcessSpawn(workspace.StubHandler{}), nil)
	defer pool.CloseAll(context.Background())

	ev := pool.Dispatch(context.Background(), newWriteCmd("ws-unknown", "c-1"))
	if ev.Kind != protocol.EventCompletedFailure {
		t.Fatalf("kind: want completed_failure got %q", ev.Kind)
	}
	if !strings.Contains(ev.FailureReason, "no workspace runner") {
		t.Errorf("failure_reason: want substring 'no workspace runner' got %q", ev.FailureReason)
	}
}

func TestPool_MultipleCommandsReuseSameRunner(t *testing.T) {
	// Count spawns by wrapping the underlying SpawnFunc.
	var spawnCount int
	var mu sync.Mutex
	inner := InProcessSpawn(workspace.StubHandler{})
	counter := func(ctx context.Context, id string) (WorkspaceRunner, error) {
		mu.Lock()
		spawnCount++
		mu.Unlock()
		return inner(ctx, id)
	}
	pool := NewPool(counter, nil)
	defer pool.CloseAll(context.Background())

	if ev := pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-1")); ev.Kind != protocol.EventCompletedSuccess {
		t.Fatalf("create: %q (reason=%q)", ev.Kind, ev.FailureReason)
	}
	if ev := pool.Dispatch(context.Background(), newWriteCmd("ws-1", "c-2")); ev.Kind != protocol.EventCompletedSuccess {
		t.Fatalf("write: %q (reason=%q)", ev.Kind, ev.FailureReason)
	}
	if ev := pool.Dispatch(context.Background(), newWriteCmd("ws-1", "c-3")); ev.Kind != protocol.EventCompletedSuccess {
		t.Fatalf("write2: %q (reason=%q)", ev.Kind, ev.FailureReason)
	}
	if spawnCount != 1 {
		t.Errorf("spawn count: want 1, got %d", spawnCount)
	}
}

func TestPool_CleanupReapsRunner_RespawnOnNextCreate(t *testing.T) {
	var spawnCount int
	var mu sync.Mutex
	inner := InProcessSpawn(workspace.StubHandler{})
	counter := func(ctx context.Context, id string) (WorkspaceRunner, error) {
		mu.Lock()
		spawnCount++
		mu.Unlock()
		return inner(ctx, id)
	}
	pool := NewPool(counter, nil)
	defer pool.CloseAll(context.Background())

	pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-1"))
	pool.Dispatch(context.Background(), newCleanupCmd("ws-1", "c-2"))
	// After cleanup, another Write for ws-1 finds no runner.
	if ev := pool.Dispatch(context.Background(), newWriteCmd("ws-1", "c-3")); ev.Kind != protocol.EventCompletedFailure {
		t.Errorf("post-cleanup write should fail-no-runner, got %q", ev.Kind)
	}
	// But a new CreateWorkspace respawns.
	if ev := pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-4")); ev.Kind != protocol.EventCompletedSuccess {
		t.Fatalf("respawn create: %q (reason=%q)", ev.Kind, ev.FailureReason)
	}
	if spawnCount != 2 {
		t.Errorf("spawn count: want 2, got %d", spawnCount)
	}
}

func TestPool_ParallelDispatchAcrossWorkspaces(t *testing.T) {
	pool := NewPool(InProcessSpawn(workspace.StubHandler{}), nil)
	defer pool.CloseAll(context.Background())

	var wg sync.WaitGroup
	var failures int
	var mu sync.Mutex
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			wsID := fmtWS(i)
			if ev := pool.Dispatch(context.Background(), newCreateCmd(wsID, "c-create-"+wsID)); ev.Kind != protocol.EventCompletedSuccess {
				mu.Lock()
				failures++
				mu.Unlock()
				return
			}
			if ev := pool.Dispatch(context.Background(), newWriteCmd(wsID, "c-write-"+wsID)); ev.Kind != protocol.EventCompletedSuccess {
				mu.Lock()
				failures++
				mu.Unlock()
			}
		}(i)
	}
	wg.Wait()
	if failures != 0 {
		t.Errorf("want 0 failures, got %d", failures)
	}
}

func fmtWS(i int) string { return "ws-" + string(rune('a'+i)) }

func TestPool_SpawnFailure_EmitsFailure(t *testing.T) {
	failingSpawn := func(context.Context, string) (WorkspaceRunner, error) {
		return nil, errors.New("disk full")
	}
	pool := NewPool(failingSpawn, nil)

	ev := pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-1"))
	if ev.Kind != protocol.EventCompletedFailure {
		t.Fatalf("want completed_failure, got %q", ev.Kind)
	}
	if !strings.Contains(ev.FailureReason, "disk full") {
		t.Errorf("failure_reason: want substring 'disk full' got %q", ev.FailureReason)
	}
}

// hangingHandler blocks the workspace's response forever — used to test
// ctx cancellation while a Send is in-flight.
type hangingHandler struct{ workspace.StubHandler }

func (hangingHandler) InvokeClaudeCode(ctx context.Context, _ *protocol.InvokeClaudeCodeCommand) (map[string]any, error) {
	<-ctx.Done()
	return nil, ctx.Err()
}

func TestPool_SendContextCancel_RunnerDroppedAndFailureEmitted(t *testing.T) {
	pool := NewPool(InProcessSpawn(hangingHandler{}), nil)
	defer pool.CloseAll(context.Background())

	// First spawn the workspace via a successful CreateWorkspace.
	if ev := pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-1")); ev.Kind != protocol.EventCompletedSuccess {
		t.Fatalf("create: %q (reason=%q)", ev.Kind, ev.FailureReason)
	}

	invokeCmd := &protocol.AgentCommand{
		Kind: protocol.KindInvokeClaudeCode,
		InvokeClaudeCode: &protocol.InvokeClaudeCodeCommand{
			CommandHeader: protocol.CommandHeader{
				CommandID: "c-invoke", WorkspaceID: "ws-1", Traceparent: "tp-invoke",
				Kind: protocol.KindInvokeClaudeCode,
			},
			Limits: protocol.InvokeClaudeCodeLimits{WallclockSeconds: 1},
		},
	}
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	ev := pool.Dispatch(ctx, invokeCmd)
	if ev.Kind != protocol.EventCompletedFailure {
		t.Fatalf("want completed_failure on ctx cancel, got %q", ev.Kind)
	}
	if !strings.Contains(ev.FailureReason, "runner:") {
		t.Errorf("failure_reason: want 'runner:' prefix, got %q", ev.FailureReason)
	}
	// The cancelled runner should be dropped — a CreateWorkspace
	// respawns rather than reusing the broken one.
	if ev := pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-respawn")); ev.Kind != protocol.EventCompletedSuccess {
		t.Errorf("respawn after cancel: %q (reason=%q)", ev.Kind, ev.FailureReason)
	}
}

func TestPool_MissingWorkspaceID_Failure(t *testing.T) {
	pool := NewPool(InProcessSpawn(workspace.StubHandler{}), nil)

	cmd := &protocol.AgentCommand{
		Kind:            protocol.KindCreateWorkspace,
		CreateWorkspace: &protocol.CreateWorkspaceCommand{},
	}
	ev := pool.Dispatch(context.Background(), cmd)
	if ev.Kind != protocol.EventCompletedFailure {
		t.Fatalf("want completed_failure, got %q", ev.Kind)
	}
	if !strings.Contains(ev.FailureReason, "missing workspace_id") {
		t.Errorf("failure_reason: %q", ev.FailureReason)
	}
}

func TestPool_CloseAll_TerminatesAllRunners(t *testing.T) {
	pool := NewPool(InProcessSpawn(workspace.StubHandler{}), nil)
	pool.Dispatch(context.Background(), newCreateCmd("ws-1", "c-1"))
	pool.Dispatch(context.Background(), newCreateCmd("ws-2", "c-2"))

	pool.CloseAll(context.Background())
	// After CloseAll, subsequent non-Create commands for those workspaces
	// fail since the runners are gone.
	if ev := pool.Dispatch(context.Background(), newWriteCmd("ws-1", "c-after")); ev.Kind != protocol.EventCompletedFailure {
		t.Errorf("post-CloseAll write should fail, got %q", ev.Kind)
	}
}
