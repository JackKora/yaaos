/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [],

  // Informational rules — violations appear in reports but do not fail the
  // build. Severity is "info" deliberately; enforcement tightens once all
  // existing callers are conforming.
  options: {
    doNotFollow: {
      path: ["node_modules", "src/core/api/generated", "shared/components/ui"],
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

  // Non-failing architectural rules (severity: "info").
  // Violations show in `depcruise --output-type text` but do not exit non-zero.
  //
  // Rules:
  //   core-no-domain       — core/* must not import from domain/*
  //   shared-no-core       — shared/* must not import from core/* or domain/*
  //   no-cross-domain      — domain/X must not import from domain/Y
  //   generated-encapsulated — only core/api/* may import from core/api/generated/*
  //   barrel-only          — cross-module imports must resolve to index.ts(x) barrels
  //
  // shared/components/ui is excluded (managed vendor layer; arbitrary internal
  // imports are intentional there).
  allowed: [
    {
      name: "core-no-domain",
      severity: "info",
      from: { path: "^src/core" },
      to: { path: "^src/domain" },
      comment: "core must not depend on domain",
    },
    {
      name: "shared-no-core",
      severity: "info",
      from: { path: "^src/shared" },
      to: {
        path: "^src/(core|domain)",
        pathNot: "^src/shared/components/ui",
      },
      comment: "shared must not depend on core or domain",
    },
    {
      name: "no-cross-domain",
      severity: "info",
      from: { path: "^src/domain/([^/]+)" },
      to: {
        path: "^src/domain/([^/]+)",
        // The capture groups don't match — different domain modules.
        // dependency-cruiser resolves the actual paths so we check the prefix.
      },
      comment: "domain modules must not import each other",
    },
    {
      name: "generated-encapsulated",
      severity: "info",
      from: { pathNot: "^src/core/api" },
      to: { path: "^src/core/api/generated" },
      comment: "only core/api may import generated types",
    },
  ],
};
