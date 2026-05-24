# M07 — Architecture

Read [requirements.md](requirements.md) first for the locked decisions referenced below as `L1`–`L22`.

## The published artifact

One image at `yaaos/yaaos-agent:<tag>`, built `FROM scratch`. The image contains exactly two files:

```
/yaaos-agent           static Go binary, CGO=0, -trimpath, version baked via ldflags
/tini                  tini-static, matched to the manifest's architecture
```

No base OS. No shell. No libc. No package manager. The image is not directly runnable in any meaningful sense — its only purpose is to be a `COPY --from=` source in a customer Dockerfile.

Per-architecture entry in the multi-arch manifest list (`linux/amd64`, `linux/arm64`) has its own pair of binaries. Customers pull a single tag; their Docker daemon transparently resolves to the right manifest entry.

## Customer integration contract

Customer's workspace Dockerfile, from any glibc-based base:

```
FROM debian:bookworm-slim                                            # or ubuntu:24.04, amazonlinux:2023, RHEL/UBI, …
COPY --from=yaaos/yaaos-agent:<version> /yaaos-agent /usr/local/bin/
COPY --from=yaaos/yaaos-agent:<version> /tini        /usr/bin/
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/yaaos-agent"]
```

What the customer adds beyond this is their domain: build tooling, language runtimes, repo checkouts, secrets, whatever. None of those interact with the agent.

What the customer does NOT do:
- Install Node (the agent installs its own).
- Install Claude Code / Codex (the agent installs its own).
- Configure PATH for any of the above.
- Set any ENTRYPOINT / CMD overrides.

## Tag grammar

Per release with version `X.Y.Z`, the pipeline pushes four tags pointing at one manifest list:

| Tag | Purpose | Mutability |
|---|---|---|
| `X.Y.Z` | exact pin | immutable (CI rejects re-push) |
| `X.Y` | latest patch on `X.Y.x` | floats forward |
| `X` | latest minor on `X.x.x` | floats forward |
| `latest` | newest release of any line | floats forward |

Customers running in production should pin `X.Y.Z` (the only immutable tag). Floating tags are for "give me whatever is current" workflows.

Architecture is never in the tag. Multi-arch manifest does that work transparently.

## Build pipeline (`agent-deploy` RWX task)

Lives in `.rwx/push.yml`. Triggers only on `event.git.ref == "refs/heads/main"` after a successful `agent-ci`. Steps:

1. **Resolve version.** Read `apps/agent/VERSION`. This is `$VERSION` for the rest of the task.
2. **Immutability guard.** Query Docker Hub for `yaaos/yaaos-agent:$VERSION`. If it exists → fail loudly with a message instructing the contributor to bump VERSION.
3. **Produce binaries.** Run `apps/agent/bin/release-build`:
   - For each arch in `amd64 arm64`:
     - `CGO_ENABLED=0 GOOS=linux GOARCH=$arch go build -trimpath -ldflags "-s -w -X main.agentVersion=$VERSION" -o apps/agent/dist/yaaos-agent-$arch ./cmd/agent`
   - Download `tini-static-amd64` and `tini-static-arm64` from `github.com/krallin/tini/releases/download/<pinned>/`, verify SHA-256 against constants in the script, place under `apps/agent/dist/`.
4. **Buildx setup.** `docker buildx create --use` (or reuse existing builder).
5. **Docker login.** `docker login -u "$DOCKERHUB_USERNAME" --password-stdin <<<"$DOCKERHUB_TOKEN"` (secrets from RWX).
6. **Multi-arch build & push.** One `docker buildx build` invocation with `--platform linux/amd64,linux/arm64 --push` and four `-t` flags for the four tags.
7. **Verify.** `docker buildx imagetools inspect yaaos/yaaos-agent:$VERSION` confirms two-arch manifest. (Belt-and-braces; the previous step would have errored if push failed, but this protects against silent partial-push weirdness.)

`apps/agent/dist/Dockerfile`:

```
FROM scratch
ARG TARGETARCH
COPY yaaos-agent-${TARGETARCH} /yaaos-agent
COPY tini-static-${TARGETARCH} /tini
```

`TARGETARCH` is provided automatically by BuildKit when `--platform` is set. The Dockerfile is platform-agnostic; the binaries differ per platform.

No `ENTRYPOINT` in this Dockerfile. The image is `COPY --from=` only — never runs on its own.

## Agent boot bootstrap

New package `apps/agent/internal/bootstrap/`. Invoked from `cmd/agent/main.go` after config parse and authentication, before the command channel opens. Sequence:

1. **Detect libc.** Read `/etc/os-release`; if `ID=alpine` or `ID_LIKE` contains a musl marker → log and exit nonzero with a clear "Alpine/musl not supported in M07" message. (Belt-and-braces: also run a quick `ldd` self-check to catch atypical musl bases that don't identify cleanly via os-release.)
2. **Resolve storage paths.** Default: `/var/lib/yaaos/{runtime/node,coding-agents}` if effective UID is 0; else `$HOME/.yaaos/{runtime/node,coding-agents}`. Override via `YAAOS_AGENT_STATE_DIR`. Create with `0o755`.
3. **Ensure Node installed.**
   - Check `<state-dir>/runtime/node/bin/node` exists and runs (`--version` prints the pinned version). If yes, skip to step 4.
   - Else download `https://nodejs.org/dist/v<nodeVersion>/node-v<nodeVersion>-linux-<arch>.tar.gz` via `net/http` (HTTPS with system CA bundle, configurable via `YAAOS_AGENT_NODE_DIST_BASEURL` for mirrors).
   - Compute SHA-256 of the downloaded blob; compare against `nodeSha256Amd64` / `nodeSha256Arm64` constants. Mismatch → abort.
   - Extract with `archive/tar` + `compress/gzip` into a temp dir; atomically rename to `<state-dir>/runtime/node/`.
4. **Ensure coding agents installed.** For each agent in the configured list (env `YAAOS_AGENT_CODING_AGENTS`, comma-separated, mapped through an internal `name → npm-package` table):
   - If `<state-dir>/coding-agents/node_modules/<pkg>/package.json` exists → log `"<pkg> already installed at <version>"` and continue.
   - Else write/update `<state-dir>/coding-agents/.npmrc` containing `registry=https://registry.npmjs.org/` (belt with the command-line `--registry` brace).
   - Invoke `<state-dir>/runtime/node/bin/npm install --prefix <state-dir>/coding-agents --registry=https://registry.npmjs.org/ --ignore-scripts <pkg>`.
   - Then `<state-dir>/runtime/node/bin/npm --prefix <state-dir>/coding-agents audit signatures`. Any failure → abort bootstrap (telemetry surfaces the failure to control plane; workspace never becomes ready).
   - Log resolved version (`require('<pkg>/package.json').version`) to OTel.
5. **Open command channel.** Bootstrap done. Normal agent serving begins.

### Storage layout

```
<state-dir>/                          (e.g. /var/lib/yaaos/)
├── runtime/
│   └── node/
│       ├── bin/node
│       ├── bin/npm
│       ├── bin/npx
│       └── lib/, share/, etc.
└── coding-agents/
    ├── .npmrc                        (registry=https://registry.npmjs.org/)
    ├── package.json                  (npm-managed)
    ├── package-lock.json             (npm-managed)
    └── node_modules/
        ├── @anthropic-ai/claude-code/
        │   ├── package.json
        │   └── …
        ├── @openai/codex/
        │   └── …
        └── .bin/                     (npm-generated CLI shims — not used by agent)
```

### Invocation contract

When the agent executes a coding agent, it never relies on `PATH` or shebangs. Always absolute path to our Node + absolute path to the package's main entrypoint:

```
<state-dir>/runtime/node/bin/node \
  <state-dir>/coding-agents/node_modules/@anthropic-ai/claude-code/cli.js \
  <args>
```

Customer can have their own Node at `/usr/bin/node` (or `/usr/local/bin/node`, or anywhere). Agent does not see it, does not use it.

## Lifecycle

`tini` is PID 1. The agent is PID 1's only child (process tree depth 2).

On `docker stop`:

1. Docker sends `SIGTERM` to PID 1 (`tini`).
2. `tini` forwards `SIGTERM` to the agent.
3. Agent's existing `signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)` path cancels its root context.
4. Agent aborts any in-flight WorkflowCommand (no graceful drain — `L12`), deregisters from the control plane, calls the deferred OTel shutdown, exits 0.
5. `tini` reaps the agent and exits 0.
6. Docker sees PID 1 exit, container stops.
7. If the agent doesn't exit within `stop_grace_period` (default 10s), Docker SIGKILLs PID 1, killing everything.

The "abort vs drain" choice is deliberate (`L12`) — workspaces are pets in concept but are not patient about shutdown in practice.

## Failure modes

| Failure | Detection | Behavior |
|---|---|---|
| Customer's base is Alpine/musl | bootstrap step 1 | Log clear error; exit nonzero; control plane sees workspace never reached ready. |
| Network down during Node download | `net/http` error | Retry with backoff (policy TBD — see [open-questions.md](open-questions.md)); eventual abort. |
| Node SHA-256 mismatch | bootstrap step 3 | Abort immediately; telemetry → control plane; do NOT fall back to whatever's on disk. |
| npm install fails | exit code | Retry once; otherwise abort. |
| `npm audit signatures` fails | exit code / output parse | Abort, do not run any coding agent. |
| Read-only `/var/lib` | `EROFS` on `os.MkdirAll` | Surface clear error directing customer to either make the path writable or set `YAAOS_AGENT_STATE_DIR` to a writable location. |
| Customer overrides ENTRYPOINT | Control plane never sees a registration | Telemetry alerts on missing registration; human investigates. We cannot mechanically prevent this. |
| Bootstrap interrupted by container kill mid-extract | next boot detects partial state | Idempotency-check is currently "does `node/bin/node --version` work" — partial extract would fail this and trigger re-download. (See [open-questions.md](open-questions.md) for stronger atomic-rename hardening.) |

## How M07 changes the existing codebase

- `apps/agent/cmd/agent/main.go`: turn `const agentVersion = "0.0.1"` (line 39) into `var agentVersion = "dev"` (ldflags-injected at release build). `YAAOS_AGENT_VERSION` env override stays as a debug escape hatch.
- `apps/agent/cmd/agent/main.go`: call `bootstrap.Ensure(ctx, cfg)` after auth and before opening the command channel.
- `.rwx/push.yml`: add the `agent-deploy` task. Keep all existing tasks unfiltered.
- `apps/agent/Dockerfile` (existing, debian-slim + Node + Claude Code): unchanged in M07. Its future is decided post-M07 — see [open-questions.md](open-questions.md).

## How M07 interacts with M05's agent design

M07 leaves the M05 wire protocol, control-plane contract, and workspace lifecycle untouched. The only agent code that changes is:

- Boot sequence (add bootstrap step).
- Version handling (linker-injected instead of source constant).

The "agent has zero business logic" principle holds — bootstrap is local-ops only. No control-plane involvement.

## Verification

Manual on the first release:

1. Bump `apps/agent/VERSION` to `0.0.1`. Merge to main.
2. Watch `agent-deploy` in RWX. It must pass; if it fails verify the secret provisioning before retrying.
3. From a Debian VM: `docker run --rm --entrypoint /yaaos-agent yaaos/yaaos-agent:0.0.1 --version` → prints `0.0.1` (proves ldflags injection + manifest resolution).
4. From an Apple Silicon dev machine: same command works (proves arm64 manifest entry).
5. Write a temporary `Dockerfile.smoke` (FROM `amazonlinux:2023` + the three-line recipe), build, run. Expect agent to:
   - Detect glibc and proceed.
   - Download Node, verify SHA, extract.
   - Install Claude Code from npm, verify signatures.
   - Register with the control plane (whatever the dev/staging control plane is at that time).
   - Print logs visible via `docker logs`.
6. Stop the smoke container with `docker stop` → agent logs show clean SIGTERM handling, exit 0, deregistration recorded by control plane.
7. Attempt a second `agent-deploy` without bumping VERSION → task fails with the immutability guard message.
8. From an Alpine smoke container: agent boots, bootstrap detects musl, exits cleanly with the unsupported-base error message.

Automated:

- Add a single e2e under `apps/e2e/` (or wherever the existing E2E suite lives) that builds the smoke image against a glibc base, runs it, asserts agent registration in the dev control plane, then sends `docker stop` and asserts deregistration. Triggered manually post-release; not on every PR.
