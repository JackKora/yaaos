#!/usr/bin/env node
/**
 * Dependency-cruiser enforcement gate.
 *
 * Runs the full boundary rule set from .dependency-cruiser.cjs and exits
 * non-zero if any violation is found. Uses the programmatic API directly
 * (rather than the depcruise CLI) so it runs from the pnpm workspace without
 * a global install.
 *
 * `validate: true` is REQUIRED — without it cruise() builds the dependency
 * graph but never applies the ruleSet, so every run reports 0 violations.
 */
import { cruise } from "dependency-cruiser";
import { createRequire } from "module";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

const config = require(join(__dirname, "../.dependency-cruiser.cjs"));

const result = await cruise(["src"], {
  validate: true,
  ruleSet: { forbidden: config.forbidden },
  ...config.options,
});

const violations = result.output.summary.violations;

if (violations.length === 0) {
  console.log("  dependency-cruiser: 0 violations ✓");
  process.exit(0);
}

console.error(`  dependency-cruiser: ${violations.length} violation(s) found:`);
for (const v of violations) {
  console.error(`    [${v.rule.name}] ${v.from} → ${v.to}`);
}
process.exit(1);
