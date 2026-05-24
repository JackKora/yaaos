# M07 — Requirements

## Problem

The WorkspaceAgent (Go binary shipped in M05) has no public distribution mechanism. To onboard a customer today we'd hand them a binary out-of-band. We need a way for customers to integrate the agent into their workspace containers as a normal supply-chain step:

- They write a Dockerfile that pulls our published artifact.
- They control the base image, the rest of the tooling, and the rebuild cadence.
- We control the agent version and the coding-agent runtime supply chain (Node, Claude Code, Codex), without forcing image rebuilds on every coding-agent release.

The release pipeline must be automated end-to-end: a merge to `main` produces multi-arch, multi-tag artifacts on Docker Hub, with the version derived from the repo state, not from per-release human ceremony beyond bumping a single file.

## Goals

- **Public, versioned image on Docker Hub** at `yaaos/yaaos-agent`. Multi-arch (`linux/amd64`, `linux/arm64`). Customers pull by tag, never by sha.
- **Minimal customer integration contract** — a Dockerfile recipe a customer can paste and modify only by changing their `FROM`.
- **Coding-agent freshness decoupled from image rebuilds.** When Anthropic ships Claude Code v1.7.5, customers on existing images get it on next workspace restart, with no rebuild on either side.
- **Automated release pipeline.** Merge to main → tested → built → published. No manual `docker push` ceremony.
- **Verifiable supply chain.** Every artifact we ship and every artifact our agent fetches at runtime is integrity-checked.

## Non-goals (out of scope for M07)

- Per-distro convenience images (Debian, Ubuntu, AL2023 variants). One scratch image is enough.
- Batteries-included image with Node + Claude Code baked in. Out — the agent self-bootstraps.
- Alpine / musl support. Glibc-only.
- 32-bit architectures (`linux/arm/v7`, `linux/386`). Out.
- Air-gapped customer support. The agent assumes outbound internet to npm registry and nodejs.org on first boot. Air-gap support is a separate later effort with its own design.
- Image signing via cosign / Sigstore, SBOM publication. Worth doing later; not part of M07.
- Mid-life coding-agent updates (re-checking Claude Code version after boot). Boot-time install only; restart for refresh.
- Coding-agent version pinning by control plane. Always `@latest` at first boot in M07.
- Self-update of the yaaos-agent binary itself. Customers rebuild their image to upgrade the agent.

## Locked decisions

| # | Decision | Reason |
|---|---|---|
| L1 | One Docker Hub repo: `yaaos/yaaos-agent`. | Tags differentiate variants. One repo keeps pull stats, scanning, and discovery cohesive. |
| L2 | One image variant: `FROM scratch`, contents = `/yaaos-agent` + `/tini`. | Zero upstream-distro patch surface. Customer brings their own base. |
| L3 | Customer Dockerfile is exactly four lines: FROM + two COPY-from + ENTRYPOINT. | Minimal integration friction. Everything else is the customer's domain. |
| L4 | Multi-arch: `linux/amd64`, `linux/arm64`. Single Docker manifest list per tag. | Covers every modern Linux host. Arch is invisible to customers. |
| L5 | Tag grammar per release: `X.Y.Z`, `X.Y`, `X`, `latest`. `X.Y.Z` is immutable; others float. | Standard semver pattern. Forces deliberate version bumps; lets customers choose pin strictness. |
| L6 | Version source: `apps/agent/VERSION` file (single-line semver). Bumped by hand in the same PR that should publish. | One source of truth. Same value drives ldflags injection and Docker tags. |
| L7 | Immutability guard: `agent-deploy` task fails if `yaaos/yaaos-agent:<VERSION>` already exists on Docker Hub. | Forces VERSION bump. Prevents accidental tag overwrites. |
| L8 | `agent-deploy` RWX task triggers only on push to `refs/heads/main`. Depends on `agent-ci` (test/lint/vuln must pass). | Releases are the merge artifact. Failed CI = no publish. |
| L9 | Go binary built with `CGO_ENABLED=0`, `-trimpath`, `-ldflags "-s -w -X main.agentVersion=$VERSION"`. | Universal Linux compatibility. Reproducible build. Version baked into binary. |
| L10 | `tini-static` (not the dynamically-linked `tini`) shipped in the scratch image. | Universal libc-independence. Tini's only job: forward signals to PID 1's child, reap zombies. |
| L11 | PID 1 model: `tini` is PID 1 (via ENTRYPOINT), agent is its sole child. | Avoids the Go PID-1 zombie-reaping risk without bringing back a supervisor. |
| L12 | SIGTERM handling: abort in-flight WorkflowCommand, deregister from control plane, flush OTel, exit 0. No graceful drain. | Workspace shutdowns are not patient. Existing `signal.NotifyContext(SIGINT, SIGTERM)` path already implements this shape. |
| L13 | Agent self-bootstraps Node on first boot. Customer's Dockerfile does NOT install Node. | Agent owns the Node version and the supply chain. Customer's optional own Node install does not interfere. |
| L14 | Node pinned in agent source (`const nodeVersion`, `const nodeSha256Amd64`, `const nodeSha256Arm64`). Glibc-only, fetched from `nodejs.org/dist`. Hardcoded SHA-256 verified before extraction. Pure-Go download + extract (`.tar.gz`, stdlib `archive/tar` + `compress/gzip`). | Node is slow-moving and security-critical. We pin and verify; bump on deliberate cadence. |
| L15 | Agent self-bootstraps coding-agent CLIs on first boot via `npm install --prefix <agent-owned-dir>` (no `-g`). Configured set comes from `YAAOS_AGENT_CODING_AGENTS=claude-code,codex` (default tbd in open-questions). | Agent owns its install dir, never collides with customer's own Node/npm usage. Customer can also install Node globally; we don't see it. |
| L16 | Coding-agent install is idempotent — agent checks for the package's `package.json` first and skips if present. No version pinning; resolved version logged to telemetry. | Boot is fast on warm containers. Workspace restart = potential new coding-agent version, no other refresh mechanism in M07. |
| L17 | Supply chain hardening on every npm invocation: `--registry=https://registry.npmjs.org/` flag, `--ignore-scripts`, `npm audit signatures` after install. Bootstrap aborts on signature failure. | Defense in depth against registry compromise, dependency-confusion, install-script attacks. Loud failure beats degraded operation. |
| L18 | Bootstrap-storage layout: `/var/lib/yaaos/runtime/node/` and `/var/lib/yaaos/coding-agents/` (root-owned by default; `$HOME/.yaaos/` if agent is not root). Configurable via `YAAOS_AGENT_STATE_DIR`. | Agent-owned directory tree. No conflict with customer's own filesystem layout. |
| L19 | Coding-agent CLI invocation uses absolute paths: `/var/lib/yaaos/runtime/node/bin/node /var/lib/yaaos/coding-agents/node_modules/<pkg>/<entrypoint.js>`. Never relies on `PATH` or `#!/usr/bin/env node` shebang. | Total isolation from customer's Node install (if any). Deterministic. |
| L20 | Customer's workspace base must be glibc-based (Debian, Ubuntu, AL2023, RHEL, Fedora, SUSE, Arch — anything except Alpine/musl). Agent refuses to bootstrap on detected musl. | Node's official builds are glibc-only. Unofficial musl Node builds weaken the supply-chain story. Alpine deferred. |
| L21 | Docker Hub credentials in RWX as secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`. Token scoped to write-access on `yaaos/yaaos-agent` only. | First Docker registry secrets in this repo. Least-privilege scope. |
| L22 | Existing `apps/agent/Dockerfile` (debian-slim + Node + Claude Code) is NOT modified, NOT published, and its future is decided after M07 ships (see open-questions). | Out of scope to rework existing image in M07. Decision deferred. |

## In scope (deliverables)

1. **`apps/agent/VERSION`** — single-line semver file.
2. **`apps/agent/dist/Dockerfile`** — scratch image, multi-arch via `TARGETARCH` build arg.
3. **`apps/agent/bin/release-build`** — script that produces both binaries (CGO=0, ldflags-injected version) + fetches & SHA-verifies `tini-static` for both arches.
4. **`apps/agent/cmd/agent/main.go`** — change `const agentVersion` → `var agentVersion = "dev"` so ldflags can override at link time.
5. **`apps/agent/internal/bootstrap/`** — new package implementing the boot-bootstrap sequence (libc detection, Node download/verify/extract, coding-agent install via npm with hardened flags, idempotency check).
6. **`.rwx/push.yml`** — add `agent-deploy` task (triggered only on merge to main, depends on `agent-ci`, builds + pushes multi-arch + multi-tag).
7. **`apps/agent/docs/distribution.md`** — per-module-style doc covering the published artifact, customer recipe, tag grammar, immutability rule, SIGTERM lifecycle, version bump procedure.
8. **`apps/agent/docs/bootstrap.md`** (new) — describes the boot-time bootstrap of Node + coding agents, the storage layout, the supply-chain hardening, and the glibc-only constraint.
9. **`apps/agent/docs/README.md`** — index entries linking to the two new docs.
10. **`docs/system-architecture.md`** — one section update naming Docker Hub as the publish target and the scratch + `COPY --from=` pattern as the customer integration contract.
11. **Docker Hub README** for `yaaos/yaaos-agent` — the customer-facing copy on the Docker Hub page itself (separate from the in-repo doc).

## Open questions (resolved during implementation or by explicit owner decision)

See [open-questions.md](open-questions.md) for the full enumerated list. Themes:

- Docker Hub org ownership and bot account.
- Default coding-agent set in `YAAOS_AGENT_CODING_AGENTS`.
- Codex npm package name verification (the actual published name).
- Bootstrap retry policy for transient network failures (npm, nodejs.org).
- Corporate-proxy support (HTTP_PROXY env vars).
- DNS resolution under Go's pure-Go resolver (CGO=0 implication).
- Read-only filesystem detection and error surface.
- Whether agent-deploy needs a manual approval gate.
- Cosign signing / SBOM publication for the image itself.
- Disposition of existing `apps/agent/Dockerfile`.
- Rate-limit considerations for customer pulls (Docker Hub anonymous pull cap).
- Tini version pin source + bump procedure.

## Drivers (recap from README)

- M05 ships the agent but no publication path. M07 closes that gap.
- Coding agents ship daily; image-baked versioning is structurally wrong for them. Runtime self-bootstrap fixes it.
- Existing `apps/agent/Dockerfile` is the wrong shape for customer distribution (couples our cadence to Debian's and Anthropic's). It can stay for internal use or be retired — decided after M07.

## Reading order continues in [architecture.md](architecture.md).
