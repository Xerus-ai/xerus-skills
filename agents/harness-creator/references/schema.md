# Harness schema (v1)

This is the schema for the files the skill creates. `scripts/harness_check.py` enforces everything
marked **[E]** (error) or **[W]** (warning). Paths are relative to the harness root (default
`harnesses/`).

## `registry.yaml`

```yaml
schema_version: 1
harnesses:
  - {entry}
  - {entry}
```

- **[E]** The file exists and has a top-level `harnesses:` list (it may be empty).
- **[E]** Ids are unique across all entries, including retired ones.

### Entry fields

| Field | Type | Required | Rule |
|-------|------|----------|------|
| `id` | string | yes | **[E]** kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`), unique |
| `name` | string | yes | **[E]** non-empty |
| `project` | string | yes | **[E]** non-empty. The repo or project it serves |
| `status` | enum | yes | **[E]** one of `unproven`, `active`, `retired` |
| `version` | int | yes | **[E]** an integer >= 1. Bumped on update and modify |
| `created_at` | date | yes | **[E]** `YYYY-MM-DD` |
| `updated_at` | date | no | **[E]** `YYYY-MM-DD` if present |
| `description` | string | yes | **[E]** non-empty, not a placeholder |
| `runbook` | map | yes | **[E]** all six keys (see below), each an acceptable answer |
| `capabilities` | list[string] | yes | **[E]** non-empty; every item is a non-empty string and not a placeholder |
| `intake` | list[path] | yes | **[E]** non-empty; each file exists under the root. The first item is the birth certificate |
| `definition` | path | no | **[E]** if present, the file exists, its `id` equals the entry id and its `version` equals the entry version |
| `blocking_facts` | list[string] | no | **[E]** must be absent or empty when `status: active` |
| `retired` | map | when retired | **[E]** when `status: retired`: `at` (date) and `reason` (non-empty) are required; `replaced_by` is optional (an id) |
| `depends_on` | list[id] | no | **[W]** each id should exist in the registry |
| `source` | map | no | Free-form: `workflow`, `command`, `hooks`, `state_files`, ... (what it wraps) |
| `tags` | list[string] | no | |

**[E]** `status: active` requires a `definition` in which every seeded failure is `proven: true`
with a `proof`.

### Runbook keys

`how_to_run` (R1), `stage_and_scale` (R2), `live_env_access` (R3), `qa_method` (R4), `roadmap` (R5),
`guardrails` (R6).

**[E]** An acceptable answer is a string that is either:
- **specific**: at least 8 characters, and **not a placeholder**. Placeholders are: blank; an
  opening deferral word, meaning uppercase `TBD`/`TBA`/`TODO`, or any case standing alone or
  followed by a separator (`:` `-` `(` `,` `;` `.` `!` `?`), or a leading `?` (so `TBD - ask ops`
  and `todo: fill in` fail, while `Todo app backend API` passes); a bare `unknown`, `none`,
  `standard`, `the usual`, `as usual`, `same as before`, `-` or `...`; and any leftover
  `{template braces}`. Or:
- **an explicit N/A**: `N/A` followed by a reason that is itself at least 8 characters and not a
  placeholder, e.g. `N/A (read-only local transform; touches no live system)` or
  `N/A (blocked: no feedback source exists yet)`. `N/A (TBD later)` fails.

The same test applies to `description` and to each `capabilities` item.

Runtime parameters in an answer (a run id, a branch name) are written as `<run-id>`, not `{run-id}`,
because braces are reserved for unfilled template slots.

Not machine-checkable: whether an answer was *inferred* rather than told or discovered. That is the
agent's judgment. A discovered fact cites its source in the intake transcript.

## `{id}.yaml` (definition)

```yaml
id: {id}
version: 1
description: >-
  {what the pipeline does, end to end}
nodes:
  - id: plan
    type: ai                 # ai | deterministic | human_gate | verifier
    phase: plan              # free-form grouping label
    description: >-
      ...
    inputs: [...]
    outputs: [...]
    constraints: [...]
    fresh_session: false
    read_only: true
    depends_on: []
terminal_states:
  success: "..."
  blocked: "..."
constraints: [...]           # hard stops: budget cutoff, max attempts, never-touch paths
capability_blocks:           # optional; see capability-blocks.md
  - block: wiring-map
    adopted: true
    reason: "..."
seeded_failures:
  - id: sf-1
    kind: postcheck-fails-missing
    test: "..."
    proven: false
    proof: ""
    proven_at: null
```

### Definition rules

- **[E]** `id` and `version` match the registry entry that points to the file.
- **[E]** `nodes` is a non-empty list with unique `id`s, and each `type` is one of `ai`,
  `deterministic`, `human_gate`, `verifier`.
- **[E]** A `deterministic` node has a non-empty `command` and an `on_failure.prompt`.
- **[E]** A `verifier` node has `fresh_session: true`, `read_only: true`, `unskippable: true` and
  `exemptions: none`.
- **[E]** A `human_gate` node has `terminal_on_reject: true` and a `terminal_state` that is declared
  in `terminal_states`.
- **[E]** Every `depends_on` entry names a node id in the same file.
- **[E]** The **last** node is `deterministic` (the postcheck).
- **[E]** `terminal_states` is a map that includes `success`. Its keys come from `success`,
  `blocked`, `approval-required`, `exhausted`, `no-progress`, `clean-no-op`.
- **[E]** `seeded_failures` has at least 3 items with unique ids. Each `kind` is one of
  `verifier-rejects-bad`, `verifier-approves-good`, `deterministic-fails-broken`,
  `postcheck-fails-missing`, `other`. When `proven: true`, `proof` must be non-empty.
- **[E]** Required kinds: `postcheck-fails-missing` always; `verifier-rejects-bad` if there is a
  verifier node; `deterministic-fails-broken` if there is a deterministic node besides the last one.
  (The checker requires that kind once; writing one per deterministic node is the agent's job.)
- **[E]** Each `capability_blocks` item has `block`, a boolean `adopted` and a non-empty `reason`.
- **[W]** There is an `ai` node that is not `read_only: true`, and no `verifier` node (a
  self-verification risk).
- **[W]** There is a `*.yaml` file in the root that no registry entry references (an orphan
  definition).

## Intake transcripts

`intake/{id}-{verb}-{YYYY-MM-DD}.md`, where the verb is one of `create`, `update`, `modify`,
`retire`. There is no enforced internal structure beyond existing, but the template in
`templates.md` is the expected shape. The checker only confirms that every path listed in an
entry's `intake:` exists.

## Manual checklist (when PyYAML is not available)

Go through each item and fix anything that fails before you call the work done.

Registry:
1. [ ] The `harnesses:` list exists; ids are unique and kebab-case.
2. [ ] Each entry has id, name, project, status (unproven/active/retired), an integer version >= 1,
   a `created_at` date and a description.
3. [ ] All six runbook keys are present; none is blank or a placeholder; each `N/A` carries a reason.
4. [ ] `capabilities` is non-empty; `intake` is non-empty and every file in it exists.
5. [ ] If there is a `definition`, the file exists and its id and version match the entry.
6. [ ] Every `active` entry has a definition, no blocking facts, and every seeded failure proven
   with a proof.
7. [ ] Every `retired` entry has `retired.at` and `retired.reason`.

Each definition:
8. [ ] Nodes are non-empty, ids are unique, and types are valid.
9. [ ] Each deterministic node has `command` + `on_failure.prompt`.
10. [ ] The verifier (if any) is fresh_session, read_only, unskippable, with `exemptions: none`.
11. [ ] Each human gate has `terminal_on_reject: true` and a declared `terminal_state`.
12. [ ] The last node is deterministic (the postcheck); `terminal_states` includes `success`.
13. [ ] There are at least 3 seeded failures, the required kinds are present, and every proven
    one has a proof.
