# M07 — Open questions

Every item here is something we deliberately deferred during the design conversation. Each has a recommended default for "if we don't get to it, do this," plus the decision criteria for an explicit choice. Resolve during implementation, in a follow-up planning round, or by surfacing to the owner.

## A. Docker Hub & publishing

### A1. Who owns the `yaaos` org on Docker Hub?

The image will live at `yaaos/yaaos-agent` (URL confirmed: `hub.docker.com/repository/docker/yaaos/yaaos-agent`). Before `agent-deploy` can run, someone (presumably Jack) must:

- Confirm the `yaaos` org account exists, is paid (Docker Hub free tier has rate-limit consequences for anonymous pullers) or accept the free-tier consequences.
- Create a robot/service account for CI, or generate a scoped access token tied to a human account.
- Confirm 2FA / recovery-email arrangement for the org account.

**Recommended default:** generate a scoped access token (write to `yaaos/yaaos-agent` only) tied to a dedicated CI human account; rotate yearly.

**Open:** is there a billing decision to make about Docker Hub plan tier given anonymous pull limits affect customer adoption?

### A2. Docker Hub anonymous pull rate limits and the customer pull story.

Anonymous pulls from Docker Hub are limited (100 pulls per 6 hours per IP for unauthenticated, 200 for free accounts). Customer CI pipelines pulling our image at scale could hit this.

**Options:**
- Accept it for POC; document "authenticate to Docker Hub in your build" as a customer note.
- Mirror via GitHub Container Registry (`ghcr.io/yaaos/yaaos-agent`) in parallel — free, no anon pull limits, also gives us a backup if Docker Hub has an outage.
- Mirror via AWS ECR Public — free, no pull limits for public images.

**Recommended default:** Docker Hub primary in M07, document the limit, plan a `ghcr.io` mirror in a later milestone if it becomes a real complaint.

### A3. Docker Hub README content.

The Docker Hub page itself has a Markdown README field separate from any in-repo doc. It's the page a customer hits when they search Docker Hub. Needs to be written and kept in sync.

**Open:** sync mechanism — manually paste from `apps/agent/docs/distribution.md`, or push via `docker hub readme update` API as part of `agent-deploy`?

**Recommended default:** automate via the unofficial `peter-evans/dockerhub-description` Action or equivalent shell call in `agent-deploy`, sourcing from a dedicated `apps/agent/dist/DOCKERHUB_README.md` (kept narrow — different audience than the in-repo doc).

### A4. Approval gate for `agent-deploy`?

Every merge to main publishes. Is that what we want, or should there be a manual "promote" step?

**Tradeoffs:**
- **Auto-publish on merge (current plan):** Simple, no human bottleneck, version bump is the gating signal. Risk: a bad version slips out fast.
- **Manual approval:** Adds friction. Useful if releases are rare or risky. RWX-supported?

**Recommended default:** auto-publish for POC. The VERSION-bump-required design already forces deliberate intent. Revisit if we ever publish a broken release.

### A5. Cosign image signing.

`docker buildx imagetools` supports cosign signing during push. Adds verifiable provenance for the image itself (separate from the npm provenance we already do at runtime).

**Recommended default:** skip in M07, add as a follow-up milestone alongside SBOM publication. Note in `apps/agent/docs/distribution.md` that it's coming.

### A6. SBOM publication.

`docker buildx build --sbom=true` attaches an SBOM. Useful for enterprise customers running supply-chain audits.

**Recommended default:** skip in M07, follow-up.

### A7. Container image vulnerability scanning.

Trivy / Grype / Docker Scout against the published image. With a scratch base containing only our binaries, vulnerability surface is near-zero, but scanning is still a useful posture signal.

**Recommended default:** add a `trivy image yaaos/yaaos-agent:$VERSION` step at the end of `agent-deploy`, fail the task on HIGH/CRITICAL. Cheap and worth doing.

## B. Versioning & release process

### B1. Pre-release tags (RC / beta / nightly).

Do we need `0.0.1-rc1`, `0.0.1-beta`, or nightly builds for internal dogfooding?

**Recommended default:** skip in M07. Release on merge, period. Pre-release introduces a parallel publish path and complicates the immutability guard. Add later if needed.

### B2. VERSION-bump enforcement on PRs.

Right now nothing stops a contributor from merging without bumping VERSION. They'd find out at `agent-deploy` time when the immutability guard fails — but the failure is post-merge, and they'd then have to make a follow-up PR.

**Options:**
- A PR check that diffs `apps/agent/VERSION` against `main` and fails the PR if (a) backend/agent code changed and (b) VERSION did not.
- An RWX precheck task that runs on PRs and surfaces the failure earlier.
- Leave it; only catch at deploy time.

**Recommended default:** add a small precheck in `agent-ci` or a new `agent-version-check` task that runs on PRs only and fails if VERSION wasn't bumped when agent source changed. Cheap.

### B3. What does "agent source changed" mean for B2?

Probably `git diff main -- apps/agent/cmd apps/agent/internal apps/agent/go.mod apps/agent/go.sum`. Doc-only changes shouldn't require a bump. Tests? Probably not.

**Open:** exact path glob.

### B4. Backporting / multi-major-line support.

If we ship `1.x.x` and customers stay on `0.x.x`, do we ship security patches as `0.x.y`? That means publishing alongside `1.x.x` lines, and the `0` floating tag floating forward inside the 0.x line only.

**Recommended default:** explicitly out of scope for M07. Single active major line. Document that older majors are unsupported.

### B5. Tini version pin source & bump procedure.

Tini's pinned version is constants in `apps/agent/bin/release-build`. Bumping requires editing two SHA constants (one per arch) and the version string.

**Open:** is there a clean way to source these from upstream automatically (Dependabot, Renovate)? Or is "human checks tini releases every few months" enough?

**Recommended default:** human bump. Tini releases are rare (months apart). Document in `apps/agent/docs/distribution.md`.

### B6. Node version pin: same question.

`const nodeVersion = "22.13.1"` in Go source plus two SHA-256 constants. Need to know what cadence to bump on.

**Recommended default:** track Node 22 (current LTS) and bump on each patch release of the LTS line. Document the cadence.

### B7. What happens when our pinned Node version reaches EOL?

Node 22 LTS goes EOL April 2027. We must migrate to the next LTS (Node 24 or whatever) before then. Add a calendar reminder when we pin a new major.

**Recommended default:** track in a follow-up roadmap item; not an M07 deliverable.

## C. Boot bootstrap edge cases

### C1. Read-only filesystem detection.

Some hardened customer environments mount `/` read-only. Agent's `os.MkdirAll("/var/lib/yaaos/...")` fails with `EROFS`. What's the error surface?

**Recommended default:** detect `EROFS`, log a clear "set YAAOS_AGENT_STATE_DIR to a writable path (e.g., a tmpfs or volume mount)" message, exit nonzero. Document in `apps/agent/docs/bootstrap.md`.

**Open:** do we want to *fall back* to `/tmp` automatically? Probably no — silent path drift is surprising. Make the customer opt in explicitly.

### C2. tmpfs `/tmp` as fallback?

Some workspaces have writable `/tmp` (tmpfs) but read-only everywhere else. Could be a sensible default state-dir there for ephemeral workspaces.

**Recommended default:** customer sets `YAAOS_AGENT_STATE_DIR=/tmp/yaaos` if that's their model. No silent fallback from agent.

### C3. Partial-extract recovery.

If container is killed mid-Node-extract, next boot sees a half-populated `runtime/node/` directory. The current "does node --version run" check would fail, triggering re-download. Good. But what if extract is half-done with a `bin/node` that exists but is corrupt?

**Recommended default:** harden the extract path — extract to a temp directory under the state dir, atomically `os.Rename` to the final path only after extraction completes. Already mentioned in architecture.md; flagged here as something to actually implement carefully.

### C4. Partial npm install recovery.

`npm install --prefix` is generally atomic-ish (npm stages then renames), but interrupted installs can leave partial node_modules. Next boot's "does `package.json` for the package exist" check might pass even for a broken install.

**Recommended default:** treat `npm audit signatures` as the integrity check — if it fails on a boot that thought the install was already done, blow away the package's directory and reinstall once. Document the recovery path.

### C5. Idempotency check granularity.

Current architecture says "check `<pkg>/package.json` exists, skip if so." More robust: check the package's listed bin shim is executable, or run `<pkg> --version` and assert it returns non-error. Trade simplicity for reliability.

**Recommended default:** `package.json` exists + `package.json` has a valid `version` field. Simple, catches the common partial-install case.

### C6. Initial bootstrap duration budget.

First-boot bootstrap is ~30MB Node download + ~50MB Claude Code install + signature verification. Realistic time: 30-90 seconds. Is that OK for "workspace ready" SLA?

**Recommended default:** OK for POC. Telemetry captures bootstrap duration so we can baseline. If 90s is too slow, consider baking Node into the scratch image as a follow-up (gives up some of the "agent owns everything" purity but cuts startup time substantially).

### C7. Bootstrap retry policy.

Transient network errors during Node download or npm install — what's the retry policy?

**Recommended default:** exponential backoff, 3 attempts, max 30s total. Beyond that, fail the bootstrap and let the workspace orchestrator decide whether to restart the container.

### C8. Corporate proxy support.

Customer environments often funnel outbound HTTPS through a proxy. Agent's `net/http` and the subprocess `npm` both need to honor `HTTPS_PROXY` / `HTTP_PROXY` / `NO_PROXY`.

- Go's `net/http` reads `HTTPS_PROXY` env var via `http.ProxyFromEnvironment` if configured. Need to ensure our HTTP client uses it.
- npm reads `https-proxy` from npmrc or `HTTPS_PROXY` env var. Need to pass-through.

**Recommended default:** ensure both honor env-var-based proxy config out of the box, document in `apps/agent/docs/bootstrap.md`. No custom proxy config — env vars only.

### C9. Custom CA bundle for proxy.

Corporate proxies often do TLS interception with a custom root CA. Customer needs to inject CA bundle.

**Recommended default:** if customer mounts certs into `/etc/ssl/certs/`, both Go (via system CA pool) and Node (via `NODE_EXTRA_CA_CERTS` env var) honor them. Document the convention.

### C10. DNS resolution under CGO=0.

With `CGO_ENABLED=0`, Go uses its pure-Go DNS resolver, which doesn't fully honor `/etc/nsswitch.conf` or NSS plugins. This affects the agent's ability to resolve hostnames defined via LDAP/AD-backed NSS.

**Recommended default:** accept it; document that customers with NSS-backed name resolution will not see those names from the agent. Workaround: add to `/etc/hosts`. Realistically zero customers will hit this for a coding-workspace control-plane endpoint.

### C11. IPv6 vs IPv4.

Some customer networks are IPv6-only. Go's resolver tries both AFAIK. Worth verifying agent + npm both work in IPv6-only.

**Recommended default:** assume yes, test once with the smoke container in IPv6-only mode, document.

### C12. `node:` URL prefix.

In recent Node versions, the new ESM-style `import 'node:fs'` resolves natively but the old CommonJS `require('fs')` still works. Claude Code's exact bundle might be ESM. Just a thing to be aware of when invoking — we shouldn't be re-resolving its imports manually.

**Recommended default:** non-issue; we invoke the package's main entrypoint and let Node figure out the rest.

## D. Coding-agent details

### D1. Default for `YAAOS_AGENT_CODING_AGENTS`.

The env var lets customers configure which coding agents to install on boot. What's the default?

**Options:**
- `claude-code` only — minimum surface, fastest boot.
- `claude-code,codex` — broader default, slower boot.
- Empty default — customer must explicitly opt in.

**Recommended default:** `claude-code` only as the default. Customers who want Codex set the env var. Justification: most workspaces will use one or the other, and unused installs waste boot time + supply-chain surface.

### D2. Codex npm package name verification.

The architecture doc says `@openai/codex` — needs verification. There's an `@openai/codex-cli` and possibly other names. Check before shipping.

**Action:** confirm exact package name by running `npm view @openai/codex` (and variants) before locking the internal name→package map.

### D3. Internal `name → npm-package` registry location.

Where does the table live in Go? Recommended: `apps/agent/internal/bootstrap/agents.go` with a typed struct array. Easy to add new coding agents (just append).

### D4. Support for non-npm coding agents (Aider, Cursor agent, etc.).

Aider is `pip install aider-chat`. Cursor agent is a binary download. Future coding-agent additions may not be npm-distributed.

**Recommended default:** out of scope for M07. M07 ships npm-installer plumbing only. Add a pluggable "agent installer interface" in a later milestone when the second non-npm agent is real.

### D5. Pre-release coding agent versions.

What if a customer wants Claude Code 1.8.0-beta? Currently we install `@latest` which means stable.

**Recommended default:** not a concern in M07 (no version pinning). Adding pinning later opens this door.

### D6. Locale / timezone for the coding agent's runtime.

Some Node-based tools care about `LANG`, `TZ`. Worth setting `LANG=C.UTF-8` and `TZ=UTC` by default for the subprocess environment we spawn coding agents in.

**Recommended default:** set both defaults in the subprocess env; document that customers can override.

### D7. Memory limits for the Node subprocess.

Long Claude Code sessions can use multi-GB. Should we set `NODE_OPTIONS=--max-old-space-size=...` defaults?

**Recommended default:** don't set anything. Use whatever Node's default heap limit is. Customers tune via env var if they hit OOMs.

### D8. Persistent state across coding-agent invocations.

Where does Claude Code put its session state, history, MCP config, etc.? `~/.config/claude-code/`? We need to make sure that's writable too.

**Action:** verify Claude Code's state-dir conventions and ensure either `$HOME` is writable or we set `XDG_CONFIG_HOME` and `XDG_DATA_HOME` to agent-owned paths.

## E. Supply chain

### E1. npm provenance attestation coverage.

The plan says we use `npm audit signatures` and abort on failure. This assumes both `@anthropic-ai/claude-code` and `@openai/codex` ship Sigstore provenance attestations.

**Action:** before locking the design, verify both packages currently ship provenance. If one doesn't, decide whether to (a) accept registry-signature-only for that package, or (b) refuse to onboard that agent until upstream fixes it.

### E2. npm registry fallback.

If `registry.npmjs.org` has an outage, do we want a fallback?

**Recommended default:** no fallback. Outages are rare and short. Bootstrap fails, workspace doesn't come up, customers see the npm outage like the rest of the world.

### E3. Tarball cache reuse.

Each boot downloads Node fresh if not present. Should we cache the tarball in case the install path gets nuked but the cache survives?

**Recommended default:** no cache. The install dir IS the cache (idempotency check). Container deletions are rare enough that re-download cost is acceptable.

### E4. Pinning npm itself.

Node ships with a bundled npm version. Bumping Node pin = bumping npm version. Fine.

**Open:** if Anthropic ever publishes a Claude Code release that requires a newer npm than the one bundled in our pinned Node, we'd have to bump Node. Acceptable, but worth being aware of.

### E5. Vendoring the coding-agent npm package?

Could we tarball the npm package ourselves, ship it in the scratch image, and skip the runtime npm install? Pros: deterministic, offline-capable. Cons: defeats the "no rebuild needed for new coding-agent releases" benefit we built the whole bootstrap for.

**Recommended default:** no. Keep runtime install. Vendoring is a path for air-gap support in a future milestone.

## F. Customer recipe & docs

### F1. README on Docker Hub.

Already covered in A3. Worth re-flagging that it's a distinct artifact from `apps/agent/docs/distribution.md`.

### F2. Example Dockerfiles per distro.

Distribution doc should show example recipes for at least Debian, Ubuntu, AL2023, and explicitly call out that they're identical except for the `FROM` line.

### F3. Recipe for customer who wants their own Node installed too.

Customer might `apt install nodejs` for their own scripts. The recipe should mention that this is fine — the agent uses its own Node and doesn't touch theirs.

### F4. Customer's PATH expectations.

Document that the agent does not modify `PATH`. Customer's tools work on their PATH; agent's tools (Node, claude-code, codex) are not on it. If a customer wants to run claude-code from their shell, they invoke it by path or symlink it themselves.

### F5. Default `WORKDIR` and how it interacts with customer expectations.

Our scratch image has no WORKDIR. Customer's image dictates. Worth a one-liner in docs.

### F6. Customer logging story.

Agent logs to stdout (slog, per recent commits). `docker logs` shows them. Customer's own foreground processes — wait, we don't allow those. Agent is the only foreground process. Customer's build-time daemons (if any) would have to be detached, which is generally a bad pattern.

**Action:** document "if you need to run a sidecar service, use a separate container, not the same container as the agent."

### F7. Health-check endpoint?

Should the agent expose a local HTTP health endpoint for the orchestrator to query?

**Recommended default:** out of scope for M07. M05 may already have this; if not, defer.

## G. Existing `apps/agent/Dockerfile` disposition

### G1. Keep, delete, or repurpose?

The existing `apps/agent/Dockerfile` (debian-slim + Node + Claude Code + agent) was the M05 demo image. M07 makes it obsolete for customer distribution. What about internal use?

**Options:**
- Delete. The new scratch image plus the smoke-test Dockerfile cover all use cases.
- Keep as `apps/agent/Dockerfile.demo` for internal dogfooding or local testing where you want one-image everything.
- Repurpose as the e2e test image for `apps/e2e/` runs that need the agent + Claude Code in one place.

**Recommended default:** delete in M07, recreate later if a real need emerges. Reduces maintenance surface.

**Open:** does any current code or pipeline reference `apps/agent/Dockerfile`? Need to grep before deleting.

### G2. Is the existing Dockerfile referenced by `bin/dev-rebuild` or any local-dev tooling?

**Action:** grep the repo for references before deleting.

## H. RWX / CI specifics

### H1. RWX trigger syntax for "merge-to-main-only."

The existing `push.yml` triggers on `github.push` generically. For `agent-deploy` we need filtering. RWX-specific syntax — need to confirm whether `event.git.ref == "refs/heads/main"` is the right condition expression, or whether to use `event.git.branch == "main"`, or `if:` on the task.

**Action:** confirm in RWX docs before writing the task.

### H2. RWX secret storage for `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`.

The repo doesn't use any RWX secrets today. Adding our first secrets is a one-time setup that requires UI / CLI access to the RWX project settings.

**Action:** document in `apps/agent/docs/distribution.md` how the secret is provisioned (which UI / which scope / who has access).

### H3. Buildx in RWX runners.

The existing `agent-ci` task runs on `ubuntu:24.04` + `rwx/base`. Does that image have `docker buildx` available, or do we need to install it / use a different base?

**Action:** verify. Most modern Docker installs have buildx as a default plugin. If not, install via the RWX task.

### H4. QEMU for arm64 cross-build?

If the runner is amd64 and we're cross-building arm64 via buildx, we need `qemu-user-static` registered for binfmt. Alternatively, use a Go cross-compile (which is what `release-build` does) and just have buildx COPY the prebuilt arm64 binary into the arm64 manifest — no QEMU needed.

**Recommended default:** Go cross-compiles (as architecture.md describes). Buildx never executes the binary; it only packages files into a manifest. No QEMU needed.

### H5. Caching the binaries between `agent-ci` and `agent-deploy`?

Could share binaries via RWX outputs, but rebuilding from scratch in `agent-deploy` is simpler and fast (Go cross-compile is seconds).

**Recommended default:** no caching. Rebuild in `agent-deploy`.

### H6. Failure of `agent-deploy` mid-publish.

`docker buildx build --push` is mostly atomic per platform, but if amd64 pushes and arm64 fails, we end up with a tag pointing at an incomplete manifest.

**Recommended default:** rerun the task. Docker manifest pushes overwrite atomically; a successful re-run produces a valid manifest. The immutability guard runs against the existence of *any* manifest under that tag, so a partial publish doesn't lock us out — actually wait, it might. If the first failed run created a tag entry on Docker Hub, the guard would refuse the retry.

**Open:** how to distinguish "manifest exists and is correct" from "manifest exists but is partial"? Probably: query manifest, verify both arch entries are present + match expected digests. If complete, fail (idempotency). If incomplete, allow overwrite. Or simpler: have the immutability guard check happen *before* any buildx work and ALSO clean up partial publishes on retry — but that requires destructive Docker Hub API access.

**Recommended default:** for POC, treat partial-publish as a manual intervention (delete the tag from Docker Hub UI, re-run). Document. Tighten later if it happens more than once.

## I. Telemetry / observability

### I1. OTel resource attributes for bootstrap.

Bootstrap timing and outcome (success/failure, durations per step) should land in OTel traces. Service name: `yaaos-agent`. Add a `phase=bootstrap` span attribute.

### I2. Resolved Node and coding-agent versions as resource attributes.

After bootstrap, those versions should be on every subsequent OTel span as resource attributes so they're filterable in the backend.

### I3. Bootstrap failure mode in telemetry.

Make sure a bootstrap failure produces a distinct, queryable signal — separate from "agent crashed later." Probably an event with `phase=bootstrap, status=failure, reason=<reason>`.

### I4. Log redaction.

Bootstrap logs the Node URL, npm command lines, etc. None of those should contain secrets. The DOCKERHUB_TOKEN never makes it into customer containers. Sanity-check that no secret env vars are logged.

## J. Future work (out of M07, but worth noting)

- **GHCR mirror** (A2).
- **Cosign signing + SBOM** (A5, A6).
- **Pre-release tags** (B1).
- **Air-gap support** via vendored tarballs (E5).
- **Pluggable coding-agent installer interface** for non-npm tools (D4).
- **Mid-life coding-agent refresh** (control plane sends "update Claude Code now" command).
- **Coding-agent version pinning** by control plane (per-org, per-workspace, or per-WorkflowCommand).
- **Backwards-compat tooling for layout changes** when we eventually move/rename `/var/lib/yaaos/`.
- **Bundled-Node-in-scratch-image** as a startup-time optimization if bootstrap latency becomes a pain point.
