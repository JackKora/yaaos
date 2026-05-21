// yaaos WorkspaceAgent — customer-deployed Go binary.
//
// Subcommands (Phase 0b skeleton; fleshed out in M05 Phase 6):
//
//	agent supervisor     — long-poll the control plane, spawn workspace
//	                       processes, heartbeat back inventory + liveness.
//	agent workspace      — per-workspace child process; reads AgentCommands
//	                       over stdin, writes AgentEvents over stdout.
//
// Zero business logic — every threshold, prompt, lesson, depth, timeout
// comes from the control plane via payload.
package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: agent <supervisor|workspace>")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "supervisor":
		fmt.Fprintln(os.Stderr, "supervisor subcommand: not implemented (Phase 6)")
		os.Exit(1)
	case "workspace":
		fmt.Fprintln(os.Stderr, "workspace subcommand: not implemented (Phase 6)")
		os.Exit(1)
	default:
		fmt.Fprintf(os.Stderr, "unknown subcommand: %s\n", os.Args[1])
		os.Exit(2)
	}
}
