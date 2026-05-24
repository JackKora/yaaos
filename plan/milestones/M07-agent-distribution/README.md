# M07 — WorkspaceAgent distribution

> Publish the WorkspaceAgent as a public Docker image on Docker Hub so customers can integrate it into their workspace containers with three lines of Dockerfile. Agent is responsible for bootstrapping its own runtime dependencies (Node, coding-agent CLIs) on first boot — no per-distro images, no upstream-distro patch treadmill, no version drift on rapidly-shipping coding agents.

## Status

`[planned]` — design discussed end-to-end with the owner. All major decisions locked (see [requirements.md § Locked decisions](requirements.md#locked-decisions)). Open questions enumerated in [open-questions.md](open-questions.md); none are blocking.

## Reading order

1. [requirements.md](requirements.md) — what M07 ships, what's cut, locked decisions, drivers.
2. [architecture.md](architecture.md) — the published artifact, the build pipeline, the boot bootstrap, customer integration contract.
3. [open-questions.md](open-questions.md) — fine-grained details to resolve during implementation or surface for explicit decision.

## Scope at a glance

- **One Docker Hub repo:** `yaaos/yaaos-agent`. One image variant — `FROM scratch` containing the static agent binary, `tini-static`, and nothing else. Multi-arch manifest covering `linux/amd64` and `linux/arm64`.
- **Customer integration:** three-line `COPY --from=` recipe into the customer's own Dockerfile. Customer picks any glibc-based base (Debian, Ubuntu, AL2023, RHEL, etc.).
- **Agent self-bootstraps Node and coding-agent CLIs on first boot.** No build-time Node install required of the customer.
- **One new RWX task `agent-deploy`** that triggers only on merges to main, depends on `agent-ci`, builds multi-arch, pushes to Docker Hub with semver-aliased tags.
- **Version source of truth:** `apps/agent/VERSION` (single-line semver), bumped manually before merge. Immutability guarded on push.
- **Glibc-only.** Alpine bases for customer workspaces explicitly unsupported in M07 — official Node releases are glibc-only and supply-chain integrity (PGP/SHA-verified) is non-negotiable.

## What's locked

See [requirements.md § Locked decisions](requirements.md#locked-decisions). Short version:

- **Distribution model:** scratch image + `COPY --from=` (no batteries-included image, no per-distro variants).
- **Customer Dockerfile:** ~4 lines (FROM, two COPY-froms, ENTRYPOINT). Customer does not install Node, npm, or any coding agent at build time.
- **Boot bootstrap:** agent installs Node (pinned, glibc-only, SHA-verified from nodejs.org) and the configured coding-agent CLIs (claude-code, codex, etc., via `npm install --prefix`, no `-g`) on first boot. Idempotent — re-runs are no-ops.
- **Coding agents:** no version pinning; `@latest` resolves at first boot. Subsequent updates require workspace restart. Resolved versions logged to telemetry.
- **Supply chain:** explicit `--registry=https://registry.npmjs.org/` per command, `npm audit signatures` after install, `--ignore-scripts`. Abort bootstrap on signature failure.
- **PID 1 model:** `tini` as PID 1 in the customer's container, agent as its only child. SIGTERM = abort in-flight work, deregister, flush OTel, exit 0.
- **Architectures:** `linux/amd64` + `linux/arm64`, via Docker manifest list. Arch is not in the tag.
- **Tags per release:** `<X.Y.Z>` (immutable), `<X.Y>`, `<X>`, `latest` (all four float except the first).

## What's not yet decided

See [open-questions.md](open-questions.md). Themes:

- Operational details (Docker Hub org ownership, secret provisioning in RWX, smoke-test container, README for the Docker Hub page).
- Hardening details we deliberately deferred (image signing via cosign, SBOM publication, npm install retry policy, corporate-proxy support).
- Coexistence with the existing `apps/agent/Dockerfile` (the debian-slim image with Claude Code baked in) — keep, repurpose, or delete.
- Boot-bootstrap edge cases (read-only filesystems, partial-install recovery, non-glibc detection refusal).
- Promotion path (does every merge to main publish, or is there a manual approval gate?).

## Drivers (why now)

- M05 lands the WorkspaceAgent itself, but ships no public distribution mechanism. Customers cannot use it without a published image.
- Coding agents (Claude Code, Codex) ship multiple releases per week. Image-baked versioning would force customers onto a permanent rebuild treadmill. Agent-managed runtime updates decouple the cadence.
- Existing `apps/agent/Dockerfile` (debian-slim + Node + Claude Code) was a fine M05 demo image but is the wrong shape for customer distribution (couples our release cadence to Debian's CVE cadence, and to Claude Code's release cadence).
