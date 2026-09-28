# Loop file formats

All loop files live under one **loop root** in the user's repo (default `loops/`; use an existing
convention if the repo has one, and use it consistently). Layout:

```
loops/
  REGISTRY.md            one row per loop + the global pause_all flag
  {name}/
    CONTRACT.md          the loop's law (template: contract-template.md)
    receipts.md          run state header + one receipt per run, append-only
    findings.md          deduplicated findings table (one row per thing, ever)
    REPORT.md            the latest human-readable report, overwritten each run
```

Each loop writes only inside its own folder, so two loops never contend for one file. The
registry is edited by the human, or by the agent during scaffolding/graduation on the human's
instruction - never by a loop run. `scripts/check_loops.py` validates all of it.

Dates are always absolute `YYYY-MM-DD` (no "yesterday", no "last week"): receipts are read weeks
later, when relative dates have lost their anchor.

---

## REGISTRY.md

```markdown
# Loop Registry

pause_all: false        # global kill switch: true = every run of every loop exits at preflight
aggregate_daily_token_budget: 500000   # optional: ceiling across all scheduled loops per day

| Loop | Level | Trigger | Intended cadence | Budget/run | Status |
|------|-------|---------|------------------|------------|--------|
| dep-drift | L1 | manual | weekly | 60000 tokens / 15 min | active |

## Planned (not yet contracted)

| Loop | Why | Blocked on |
|------|-----|-----------|
| pr-babysitter | open PRs sit unreviewed | two weeks of L1 reports on PR flow |
```

- `pause_all` must be exactly `true` or `false`. It stops *every* run, manual or scheduled.
- Level: `L1` | `L2`. Trigger: `manual` | `scheduled` (optionally followed by detail, e.g.
  `scheduled (cron 0 6 * * 1)`); must agree with the contract.
- Status: `active` | `paused` (runs exit at preflight) | `retired` (kept for its receipts).
- A contract's `writes:` paths are relative to the repo root (the nearest folder above the loop root
  holding `.git`; without git, the folder containing the loop root).
- The Planned table is free-form: ideas that are not contracted yet. A planned loop becomes a
  row in the main table only through the loop-creator flow.

---

## receipts.md

```markdown
# {name} - receipts

acting_on: none              # target this loop is mutating right now; always none at L1
in_progress: none            # set at preflight, cleared at Record; non-none at start = crash
last_run: none               # YYYY-MM-DD of newest receipt
last_terminal_state: none    # Result of newest receipt
consecutive_crashes: 0       # only a human resets this after it hits the threshold
report_read_through: 0       # highest run # whose report the human confirmed reading
baseline:                    # optional; indented lines, each with its method
  open_prs: 3                # `gh pr list --state open --json number` from repo root
  todo_files: 27             # count of files in docs/todo/

## Run Receipts

### Run #1 — 2026-09-28
- **Result**: success
- **Scope**: L1 report-only; read {observes}; wrote {root}/{name}/ only
- **Evidence**: `git log --oneline --since=2026-09-21` (12 commits); `gh pr list` (3 open: #41 #44 #45)
- **Metric**: new_findings = 2
- **Findings**: 2 new (lockfile-drift, flaky-e2e), 1 bumped (stale-branches seen 3), 0 resolved
- **tokens_consumed**: ~22000 (estimate)
- **wall_clock_minutes**: 7
- **Collision check**: all acting_on = none
- **Prune**: no duplicates; 1 resolved (old-node-version, CI now on 22)
- **Report read**: none yet (first run)
- **Critique**: `gh` must run from the repo root, not a subfolder - encode it in Observe step 2
- **Next**: nothing pending; 1 question in REPORT Needs a decision
```

Rules the checker enforces:
- Header keys `acting_on`, `in_progress`, `last_run`, `last_terminal_state`, `consecutive_crashes`,
  `report_read_through` (an integer, never above the newest run number).
- Receipt headers are `### Run #N — YYYY-MM-DD` (em dash or hyphen), numbered 1, 2, 3... with
  non-decreasing dates, none in the future.
- Every receipt has `Result`, `Evidence`, `Metric` (`name = value`), `tokens_consumed`,
  `wall_clock_minutes`. `Result` starts with one of the six terminal states; a reason may follow
  in parentheses: `blocked (paused)`, `blocked (collision: nightly-deps)`, `no-progress (crashed)`.
- The header's `last_run` / `last_terminal_state` match the newest receipt - after every run,
  including preflight exits.
- A pause exit is still a full receipt - short, but every field present - plus that header update.
  It is the proof that the pause was respected:

```markdown
### Run #4 — 2026-10-12
- **Result**: blocked (paused)
- **Evidence**: loops/REGISTRY.md has pause_all: true; nothing else read or written
- **Metric**: n/a
- **tokens_consumed**: ~500 (estimate)
- **wall_clock_minutes**: 1
```
- `manual_runs_read` in the contract can never exceed the number of receipts that produced a real
  report (Result `success`, `approval-required` or `clean no-op`).

Evidence means something a reader can re-check: the command, and what it returned (counts, ids,
hashes). "Checked the PRs" is a claim, not evidence.

---

## findings.md

```markdown
# {name} - findings

| id | first_seen | last_seen | seen | status | summary |
|----|------------|-----------|------|--------|---------|
| lockfile-drift | 2026-09-28 | 2026-10-05 | 2 | open | package-lock.json older than package.json |
| old-node-version | 2026-09-14 | 2026-09-28 | 3 | resolved | CI pinned Node 18; now 22 (run #3) |

## lockfile-drift
- 2026-09-28 (run #1): first seen, lock 14 days older than manifest
- 2026-10-05 (run #2): still present, manifest changed again
```

- `id` is a stable kebab-case slug chosen at first sighting; it is the dedup key. Before adding
  a row, search the table for the same underlying thing under any id.
- A re-observation bumps `seen` and `last_seen` (and may add a dated line under its heading) -
  it never adds a second row. The checker fails on duplicate ids.
- `status`: `open` (needs attention) | `watching` (not yet actionable, tracked) |
  `resolved` (condition cleared, evidence in the timeline) | `noise` (known and deliberately ignored,
  so future runs stop re-reporting it).
- The per-finding `## {id}` timeline sections are optional; use them for anything seen twice.

---

## REPORT.md

Overwritten every run. This is the file the human reads; it is what "a read report" means.

```markdown
# {Display name} - run #{N}, {YYYY-MM-DD} - {terminal state}

## What changed
- NEW lockfile-drift: package-lock.json is 14 days older than package.json (evidence: ...)

## Needs a decision
- flaky-e2e has failed 3 of the last 10 CI runs. Quarantine the test, or open an issue? (L1 will not act.)

## Watching
- stale-branches (seen 3): 9 branches with no commits since 2026-08-01.

## Known noise (not re-reported)
- npm deprecation warnings in install logs.

---
Read this? Tell your agent "{name} report #{N} read" - it counts toward graduation ({read}/{required}).
```

Lead with what changed and what needs a decision. A clean no-op report is one line.
