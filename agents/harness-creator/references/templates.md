# Templates

Copy these skeletons and fill them in. Text in `{braces}` must be replaced. The checker treats
leftover braces in runbook answers, capabilities and descriptions as placeholders.

## 1. `harnesses/registry.yaml` (first creation)

```yaml
# Harness registry: one entry per harness, never deleted, ids never reused.
# Schema: see the harness-creator skill's references/schema.md.
# Status flow: unproven -> active (after every seeded failure is proven) -> retired.
schema_version: 1
harnesses: []
```

## 2. Registry entry

```yaml
  - id: "{kebab-id}"
    name: "{Short Name}"
    project: "{repo or project name}"
    status: unproven
    version: 1
    created_at: "{YYYY-MM-DD}"
    description: >-
      {One paragraph: what the harness does, for which class of work, ending in what state.}
    definition: "{kebab-id}.yaml"          # omit until the pipeline is real (honesty rule)
    runbook:
      how_to_run: "{R1: trigger/command + inputs}"
      stage_and_scale: "{R2: environment, frequency, budget per run}"
      live_env_access: "{R3: systems read/written, read-only or read-write}"
      qa_method: "{R4: how output is validated, what proof, where receipts live}"
      roadmap: "{R5: priority, what depends on it, what it depends on}"
      guardrails: "{R6: never-do list, limits, human gates}"
    capabilities:
      - "{concrete thing it can do}"
      - "{another}"
    intake:
      - "intake/{kebab-id}-create-{YYYY-MM-DD}.md"
    source:
      workflow: "{existing workflow/command file it wraps, if any}"
      hooks: []
      state_files: []
    tags: []
```

A blocked harness adds:

```yaml
    blocking_facts:
      - "{what does not exist yet and blocks activation}"
```

A retired harness adds:

```yaml
    retired:
      at: "{YYYY-MM-DD}"
      reason: "{why}"
      replaced_by: "{other-id, or null}"
```

## 3. Definition skeleton (`harnesses/{id}.yaml`)

The common plan -> implement -> verify -> ship shape. Delete the nodes the pipeline doesn't have,
but keep the verifier and the final postcheck.

```yaml
id: "{kebab-id}"
version: 1
description: >-
  {End-to-end description of the pipeline.}

nodes:
  - id: plan
    type: ai
    phase: plan
    read_only: true
    description: >-
      Produce a plan artifact: the task verbatim, the root cause with file:line references, the
      proposed change, the exact verification commands, and the risks. Planning only; no edits.
    outputs: ["{plan artifact path}"]

  - id: plan_gate
    type: human_gate
    phase: plan
    description: Human approves the plan, or rejects it with a reason (the reason goes in the receipt).
    terminal_on_reject: true
    terminal_state: approval-required

  - id: implement
    type: ai
    phase: implement
    fresh_session: true
    read_only: false
    description: >-
      FRESH CONTEXT. Reads only the approved plan. Implements it on a fresh branch or worktree
      (never the default branch). Makes the smallest change that addresses the task. No new scope.
    constraints:
      - "Max 3 attempts per issue, then terminal state exhausted"
      - "Never touch {never-touch paths}"
    depends_on: [plan_gate]

  - id: verify_tests
    type: deterministic
    phase: verify
    command: "{the project's real test command}"
    on_failure:
      prompt: >-
        Tests failed. Norm: the test command exits 0 with every assertion passing. Remediation: fix
        the code or the test's legitimate expectation. Never disable, skip or weaken an assertion.
        If a test is flaky, flag it for quarantine rather than deleting it.
    depends_on: [implement]

  - id: verify_agent
    type: verifier
    phase: verify
    fresh_session: true
    read_only: true
    unskippable: true
    exemptions: none
    description: >-
      Separate context, read-only, default REJECT. Sees only the original task, the diff and the
      check output. Writes a verdict artifact (see verifier-persona.md).
    outputs: ["{verdict artifact path}"]
    depends_on: [verify_tests]

  - id: ship_gate
    type: human_gate
    phase: ship
    description: Human reviews the diff and the verdict; approves, or rejects with a reason.
    terminal_on_reject: true
    terminal_state: approval-required
    depends_on: [verify_agent]

  - id: ship
    type: ai
    phase: ship
    read_only: false
    description: >-
      Commit on the fresh branch, open the PR (or whatever the project's ship step is), and write the
      receipt citing the commit, branch, PR/URL and verdict artifact.
    depends_on: [ship_gate]

  - id: postcheck
    type: deterministic
    phase: ship
    command: "{script that checks each claimed artifact exists}"
    description: >-
      The last word belongs to a check, not a model. It verifies: the commit exists, the branch is
      not the default and was created by this run, the PR/URL is real, and the verdict artifact is on
      disk. (For a local-merge ship with no remote: the feature commit is an ancestor of the target
      branch.) If any of these fails, the run's terminal state is blocked, not success.
    on_failure:
      prompt: >-
        Postcheck failed, so this run cannot claim success. Fix the missing artifact (the commit,
        branch, PR or verdict file) and re-run the postcheck before writing a success receipt.
    depends_on: [ship]

terminal_states:
  success: "task done, verified, shipped, postcheck passed"
  approval-required: "a human rejected at a gate"
  blocked: "a deterministic check or the postcheck failed and could not be fixed"
  exhausted: "attempt limit reached on the same issue"

constraints:
  - "Stop at 80% of the run budget and write the receipt"
  - "The verifier is unskippable: no exemptions of any kind"
  - "No success without the postcheck passing"

capability_blocks:
  - block: wiring-map
    adopted: true
    reason: "{why}"

seeded_failures:
  - id: sf-1
    kind: verifier-rejects-bad
    test: "The verifier REJECTs a diff that silences a type error and leaves the root cause untouched"
    proven: false
    proof: ""
    proven_at: null
  - id: sf-2
    kind: verifier-approves-good
    test: "The verifier APPROVEs a known-good diff (control)"
    proven: false
    proof: ""
    proven_at: null
  - id: sf-3
    kind: deterministic-fails-broken
    test: "verify_tests exits non-zero on a deliberately broken assertion"
    proven: false
    proof: ""
    proven_at: null
  - id: sf-4
    kind: postcheck-fails-missing
    test: "The postcheck fails a ship with no commit, the default branch, no PR and no verdict file"
    proven: false
    proof: ""
    proven_at: null
```

A good `proof` looks like this:
`"ran: {exact production command} against fixture {path}; exit 1; output: 'commit missing, branch is default'; 2026-01-15"`.

A postcheck is usually a short script in the project's own language. It takes the claimed commit,
branch, URL and artifact paths as arguments, checks each one (for example `git cat-file -e <sha>`,
the branch is not `main`/`master`, the artifact file exists and is non-empty), prints one line per
check, and exits non-zero if any check fails. For a local-merge ship with no remote, replace the
branch and URL checks with `git merge-base --is-ancestor <sha> main` (or whatever the target branch
is). Keep project helper scripts in `harnesses/scripts/`, or cite their path in the node's
`command`.

Write runtime parameters in answers and commands as `<name>` (for example
`harnesses/runs/<run-id>/verdict.yaml`). The checker reads `{...}` as an unfilled template slot.

## 4. Birth certificate (`harnesses/intake/{id}-create-{YYYY-MM-DD}.md`)

```markdown
# Birth certificate: {id}

Date: {YYYY-MM-DD} · Verb: create · Requested because: {trigger}

## Q1 Known knowns
- id / name: ...
- project: ...
- description: ...

## Q2 Known unknowns (asked one at a time)
- Q: ... -> A: ...

## Q3 Unknown knowns (discovered; source cited)
- {fact} (source: {file or command})

## Q4 Completeness-critic findings
- Pass 1: {finding} -> became Q2: {question}
- Pass N: no new questions (converged)

## Runbook (hard gate: every fact answered or N/A with a reason)
| Fact | Answer |
|------|--------|
| R1 How to run | ... |
| R2 Stage & scale | ... (shared, from {other-id} intake) |
| R3 Live-env access | ... |
| R4 QA method + receipts | ... |
| R5 Roadmap | ... |
| R6 Guardrails | ... |

## Capability blocks
- {block}: adopted/skipped because ...

## Outcome
Status: unproven · Definition: {written / deferred (honesty rule)} · Blocking facts: {none / list}
```

## 5. Amendment / modification / retirement transcript

```markdown
# {Update | Modification | Retirement}: {id} v{old} -> v{new}

Date: {YYYY-MM-DD} · Verb: {update | modify | retire}

## What changed and why
- ... (evidence: {receipt or failure that prompted it})

## Runbook re-verification
| Fact | Still true? | New answer (if changed) |
|------|-------------|-------------------------|

## Shape change?
{no -> status unchanged | yes -> status reset to unproven; new seeded failures: sf-N...}

## (Retire only) Impact analysis
- Fired by: ...
- Outputs consumed by: ...
- Replaced by: ...
```

## 6. Run receipt (written by each run to the R4 location)

```markdown
### {id} run {YYYY-MM-DD HH:MM} - {terminal state}
- Input: {target}
- Nodes: plan OK · plan_gate approved · implement (attempt 1) · verify_tests exit 0 · verifier APPROVE ({verdict path}) · ship_gate approved · ship · postcheck 4/4
- Evidence: commit {sha} · branch {name} · PR {url}
- Deferred findings: {deferrable findings + stated reasons, or none}
```
