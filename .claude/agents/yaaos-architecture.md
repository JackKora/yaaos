---
name: yaaos-review-architecture
description: Architecture review of a PR, document, or codebase area. Evaluates whether changes respect established conventions and boundaries, or deviate in a desirable way. Focuses on coupling, cohesion, dependency direction, module boundaries, and long-term maintainability.
disable-model-invocation: true
---

# Architecture Review

Evaluate the architectural quality of a change — not line-level correctness (that's `/my-review`), but whether the change fits well into the system's structure, respects its conventions, and moves the architecture in a healthy direction.

## Getting Started

Determine scope:
- If `$ARGUMENTS` contains a PR number or URL → review that PR's architectural impact
- If `$ARGUMENTS` contains a file path or document → review that artifact
- If `$ARGUMENTS` names a feature area → review the architecture of that area
- If empty → ask the user what to review

## Step 1 — Learn the Existing Architecture

Before evaluating anything, understand the system as it exists today. Spawn parallel agents:

- **codebase-locator**: Map the top-level directory structure, module boundaries, and key entry points
- **codebase-analyzer**: Trace dependency directions between major modules — what imports what, what calls what
- **codebase-pattern-finder**: Identify the established conventions — file organization, naming patterns, layering, how similar changes were structured before

Look for:
- Project CLAUDE.md, AGENTS.md, or architecture docs that define intended structure
- Existing ADRs (Architecture Decision Records) in `docs/`, `adr/`, or similar
- Dependency layering (e.g., Types → Config → Repo → Service → Runtime → UI)
- Module boundary patterns (how the codebase separates concerns today)

State your understanding of the architecture before proceeding:
> "Here's how I understand the current architecture and its conventions — is this accurate?"

## Step 2 — Analyze the Change

Read the change fully — every file, not just the diff. For PRs, also read the description, linked issues, and any design documents referenced.

Map the change against the existing architecture:

### Structural Fit
- Does the change follow the established module boundaries?
- Are new files placed where the codebase's conventions would expect them?
- Does it follow the existing layering and dependency direction?
- If it introduces a new pattern, is the new pattern better than the established one and worth the inconsistency?

### Coupling Analysis
- Does the change increase coupling between modules that should be independent?
- Are there new cross-boundary imports that bypass the intended dependency direction?
- Does it create hidden coupling? (shared mutable state, implicit contracts, temporal coupling)
- Could a change in one module now break another module that was previously independent?

### Cohesion Analysis
- Are related things grouped together? (high cohesion within modules)
- Does the change scatter a single concern across multiple unrelated modules? (low cohesion)
- Are there functions or files that now have mixed responsibilities?
- Would a future developer know where to find this code based on what it does?

### Boundary Integrity
- Are public interfaces (APIs, exports, contracts) clean and minimal?
- Does the change leak implementation details across boundaries?
- Are service contracts (API schemas, message formats, shared types) backward compatible?
- If this crosses service boundaries, are the contracts explicit and versioned?

### Dependency Health
- Are dependency directions acyclic? (no circular imports between modules)
- Does the change depend on concrete implementations or on abstractions?
- Are third-party dependencies introduced at the right layer? (not deep in domain logic)
- Could this dependency be replaced without rewriting the core logic?

## Step 3 — Evaluate Desirable Deviations

Not all convention breaks are bad. Evaluate whether a deviation is:

**Desirable** — the deviation improves the architecture:
- Introduces a better pattern that should eventually replace the old one
- Breaks a convention that was itself problematic (with clear rationale)
- Simplifies a previously over-engineered area
- Creates a clear migration path from old pattern to new

**Undesirable** — the deviation degrades the architecture:
- Introduces inconsistency without clear benefit
- Takes a shortcut that creates technical debt
- Copies a pattern from a different context where it made sense but doesn't here
- Makes the "wrong thing easy and the right thing hard" for future changes

For each deviation, state whether it's desirable or not and WHY.

## Step 4 — Assess Long-term Impact

Think beyond the immediate change:
- If this pattern is repeated 10 more times, does the architecture get better or worse?
- Does this change make future changes easier or harder?
- Does it increase or decrease the cognitive load for someone new to this area?
- Are there scaling implications? (data volume, team size, deployment independence)

## Step 5 — Format the Review

```markdown
## Architecture Review: [Brief description]

### Summary
[1-2 sentences on the change's architectural impact — positive, neutral, or concerning]

### Architecture Context
[Your understanding of the relevant architectural conventions and boundaries]

### Structural Assessment

#### Follows Convention
- [Pattern/boundary respected — with evidence]

#### Desirable Deviations
- [What deviates and why it's an improvement]

#### Concerns

##### 1. [Category]: [Title]
**Impact:** [What degrades if this ships as-is]
**Evidence:** `file:line` — [what specifically violates the boundary/convention]
**Suggestion:** [How to restructure to fit the architecture, or why a new convention should be adopted]

### Dependency Map
[Brief description of how the change affects module dependencies — new edges, direction violations, cycles]

### Long-term Outlook
[Will this pattern scale? Is the architecture moving in a healthy direction?]

### Positive Patterns
- [Architectural decisions done well — reinforce good structure]
```

## Step 6 — Adversarial Challenge

Before presenting, spawn the **adversarial-debate** agent to challenge your architectural assessments.

Format your concerns, deviation judgments, and coupling/cohesion claims as structured findings and pass them to the agent along with:
- The file paths and dependency traces supporting each claim
- Your understanding of the established conventions
- The diff or artifact being reviewed

The agent will:
- Verify that claimed conventions actually exist in the codebase (not assumed from other projects)
- Steel-man architectural choices — "you say this coupling is bad, but what if it's intentional for performance or simplicity?"
- Challenge deviation judgments — is something flagged as "undesirable" actually the established pattern?
- Check for contradictions — praising a pattern in one place but flagging it in another
- Verify that dependency direction claims match actual import graphs

Apply the agent's verdicts, then confirm:
- [ ] Suggestions are concrete and respect the existing architecture's intent
- [ ] Desirable vs. undesirable deviations are clearly distinguished with rationale

## Guidelines

- This is about STRUCTURE, not style — don't flag naming or formatting
- Respect the existing architecture's intent even if you'd design it differently from scratch
- Convention consistency has value — deviations need to earn their inconsistency
- A change that follows bad conventions is not necessarily good — note when conventions themselves need revisiting
- Think in terms of "what does this make easy/hard for the NEXT developer?"
- The best architectural feedback is about forces and tradeoffs, not rules
