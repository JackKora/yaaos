/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    // ── Layer / domain direction ────────────────────────────────────────────
    // core/* must not import from domain/*.
    {
      name: "core-no-domain",
      severity: "error",
      from: { path: "^src/core" },
      to: { path: "^src/domain" },
      comment: "core must not depend on domain",
    },
    // shared/* must not import from core/* or domain/*.
    // shared/components/ui/ is excluded (managed vendor layer; arbitrary
    // internal imports are intentional there).
    {
      name: "shared-no-core-domain",
      severity: "error",
      from: {
        path: "^src/shared",
        pathNot: "^src/shared/components/ui",
      },
      to: { path: "^src/(core|domain)" },
      comment: "shared must not depend on core or domain",
    },
    // domain/X must not import from domain/Y (different domain modules).
    // Mechanism: capture the importer's first path segment as $1 and forbid
    // imports whose target starts with src/domain/ but differs from $1.
    {
      name: "no-cross-domain",
      severity: "error",
      from: { path: "^src/domain/([^/]+)" },
      to: {
        path: "^src/domain",
        pathNot: "^src/domain/$1(/|$)",
      },
      comment: "domain modules must not import each other",
    },
    // Only core/api/* may import from core/api/generated/*.
    {
      name: "generated-encapsulated",
      severity: "error",
      from: { pathNot: "^src/core/api(/|$)" },
      to: { path: "^src/core/api/generated" },
      comment: "only core/api may import generated types",
    },
    // ── Module encapsulation (public-only) ──────────────────────────────────
    // A module's public surface is its public/ directory; cross-module imports
    // must target another module's public/ files. Intra-module deep imports are
    // always legal (^$2/ exclusion). shared/components/ui/ is excluded (vendor).
    {
      name: "public-only",
      severity: "error",
      from: {
        path: "^src/(core|domain|shared)/([^/]+)",
        pathNot: "^src/shared/components/ui",
      },
      to: {
        path: "^src/(core|domain|shared)/([^/]+)/",
        pathNot: [
          // The target is the importer's own module — intra-module deep imports are legal.
          "^src/(core|domain|shared)/$2/",
          // The target is in a module's public/ surface — public import is legal.
          "^src/(core|domain|shared)/[^/]+/public/",
          // Excluded vendor layer.
          "^src/shared/components/ui/",
        ],
      },
      comment:
        "cross-module imports must target the module's public/ surface; a module's non-public/ files are private",
    },
    // ── Hygiene / safety ─────────────────────────────────────────────────────
    // No circular dependencies anywhere.
    {
      name: "no-circular",
      severity: "error",
      from: {},
      to: { circular: true },
      comment: "circular dependencies are forbidden",
    },
    // Shipped code must not import test infrastructure (MSW server/handlers,
    // test-setup). Test files themselves may import it.
    {
      name: "prod-no-test-infra",
      severity: "error",
      from: {
        path: "^src/",
        pathNot: ["^src/test/", "\\.(test|spec)\\.[jt]sx?$", "src/test-setup"],
      },
      to: { path: "^src/test/" },
      comment: "production code must not import test infrastructure (src/test/)",
    },
    // Fully-disconnected files (no incoming AND no outgoing edges) are dead.
    // NB: only catches truly orphaned files — a dead module that still imports
    // something is NOT flagged; use a dedicated unused-export tool for that.
    {
      name: "no-orphans",
      severity: "error",
      from: { orphan: true, pathNot: ["\\.d\\.ts$"] },
      to: {},
      comment: "disconnected (dead) files are forbidden",
    },
  ],

  options: {
    doNotFollow: {
      path: ["node_modules", "src/core/api/generated", "src/shared/components/ui"],
    },
    moduleSystems: ["es6", "cjs"],
    tsPreCompilationDeps: true,
    externalModuleResolutionStrategy: "node_modules",
    tsConfig: {
      fileName: "tsconfig.json",
    },
    // Map path aliases declared in tsconfig.json.
    paths: {
      "@core/*": ["src/core/*"],
      "@domain/*": ["src/domain/*"],
      "@shared/*": ["src/shared/*"],
    },
    reporterOptions: {
      text: {
        highlightFocused: true,
      },
    },
  },
};
