# M05 — decisions made during autonomous run

> Append-only log of decisions made when the spec was ambiguous and certainty was below 3 of 5. Per [START_HERE.md § Decision protocol](START_HERE.md#decision-protocol).

## Format

Each entry:

```
### <Phase N> — <one-line decision summary>

- **Certainty**: <1 or 2>/5
- **Decision**: <what was chosen>
- **Alternatives considered**: <brief>
- **Why this one**: <one line>
- **Reversal cost**: <low/medium/high — how painful to undo later>
```

Keep entries terse. The user reads this at the end of the run; volume = friction.

## Entries

<!-- Append below. Do not edit prior entries. -->

### Phase 9 — image registry: GHCR with semver+latest+sha tagging

- **Certainty**: 2/5
- **Decision**: Publish the WorkspaceAgent image to GitHub Container Registry (`ghcr.io/yaaos/yaaos-agent`). Tag strategy: each release tagged `vX.Y.Z`, the latest stable also re-tagged `latest`, every CI build tagged `sha-<short>` for traceability. Customers consume the immutable `vX.Y.Z` tag in their ECS task definition; `latest` exists for getting-started flows.
- **Alternatives considered**: (a) Docker Hub — wider familiarity but rate-limited pulls hit customer ECS task launches; (b) ECR Public — AWS-native but requires customers to authenticate the otherwise-public-image case; (c) per-customer-private registry — too much friction for a free OSS-first POC.
- **Why this one**: GHCR is free for public images, has no anonymous pull rate limits, ships with GitHub Actions, supports OCI image manifests for multi-arch (`linux/amd64` + `linux/arm64`). Migrating is a registry rename if we ever change our minds.
- **Reversal cost**: low — image URL lives in ECS task definitions; customers re-pin on next deploy.

### Phase 0b — split `014_create_all_m05` into per-phase migrations

- **Certainty**: 3/5
- **Decision**: Phase 0b's migration `014_create_outbox_entries` creates only the outbox_entries table. Subsequent M05 phases add their own migrations (`015_*`, `016_*`, …) as their owning module's model lands.
- **Alternatives considered**: (a) Write all new model files now with placeholder bodies + one `014_create_all_m05` migration; (b) Defer all M05 migrations until every model is ready.
- **Why this one**: (a) would leak future-phase columns into scaffolding before they're designed, contradicting the per-phase build order; (b) leaves outbox_entries un-creatable on existing DBs, breaking `core/tasks` tests. Per-phase migrations match how M01–M03 actually shipped (multiple migrations per milestone).
- **Reversal cost**: low — migration registration is a tuple append; future migrations can consolidate if desired.
