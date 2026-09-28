# CONTRACT.md template

Copy everything between the two `=====` markers into `{root}/{name}/CONTRACT.md` and fill every
`{placeholder}` (braces = filled now, at scaffold time; `<angle brackets>` = filled by the
runner at run time - leave those as they are). The finished contract must be runnable by an agent that has never seen this skill:
the preflight, terminal states and budget rule are written into it on purpose, so a scheduled run
needs nothing but the one-line prompt "Run the {name} loop per {root}/{name}/CONTRACT.md".

Frontmatter is flat `key: value` (no nesting, no lists); ` #` starts a comment, so never put
` #` inside a value (a description like "fix issue #12" is fine; "fix #12 #13" is cut at ` #13`). The checker
(`scripts/check_loops.py`) parses exactly these keys, so do not rename them.

=====
---
name: {name}                         # kebab-case, equals the folder name
description: {one line - what a reader gets from each run}
level: L1                            # L1 = report-only. L2 needs graduated_by/graduated_at below
observes: {what it reads - paths, commands, APIs. Read-only at L1}
writes: {root}/{name}/               # repo-relative paths, comma-separated, no spaces. L1: only this folder
trigger: manual                      # manual | scheduled (scheduled only after graduation)
intended_cadence: {daily | weekly | per release | ...}
manual_runs_required: 5              # manual runs with a human-read report before scheduling
manual_runs_read: 0                  # bumped only when the human says they read a run's report
pause_exit_proven: false             # true once a pause_all run was fired and exited cleanly
token_budget_per_run: {60000}
time_limit_minutes: {15}
crash_pause_threshold: 3             # consecutive crashed runs before the loop refuses to run
convergence_threshold: 3             # runs in a row with metric 0 before proposing a slower cadence
created_at: {YYYY-MM-DD}
graduated_by: none                   # human who authorised L2, in their words, quoted below
graduated_at: none
schedule_approved_by: none           # human who approved the scheduled trigger
schedule_approved_at: none
---

# {Display name}

## Goal
{One sentence: what the human gets from every run.}

## Non-goals
- {What this loop never does, e.g. "no fixes, no commits, no comments on PRs" at L1.}
- No re-reporting of findings already in `findings.md` unless their state changed.

## Scope
- **Reads**: {exact paths / commands / endpoints, with the working directory each runs from}.
- **Writes**: only `{root}/{name}/` (REPORT.md, findings.md, receipts.md). Nothing else, at L1.
- **Never opens**: `.env*`, key files, `secrets/`, `credentials/`, anything holding tokens -
  even to "just check". If the loop needs a credential, the tool it calls holds it.

## Baseline
Numbers the loop compares against each run live in the receipts header under `baseline:`, each
annotated with the exact command and working directory that produced it. A count without its
method gets re-derived by guessing next run.

## Workflow

### 0. Preflight (mandatory, in this order, before any other read)
A **preflight exit** below means: append a full receipt with the stated Result (every field present,
`Metric: n/a`), set the header's `last_run` (today's real date) and `last_terminal_state` to match it,
touch nothing else, stop. Leave `consecutive_crashes` and `report_read_through` as they are.

1. Read `{root}/REGISTRY.md`. If `pause_all: true`, or this loop's Status is not `active`:
   preflight exit with Result `blocked (paused)`.
2. Read the header of `receipts.md`.
   - `in_progress` is not `none` -> the previous run died without a receipt. Append a reconstructed
     receipt for it (Result `no-progress (crashed)`, Evidence = what the marker says), increment
     `consecutive_crashes`, update the header's `last_run`/`last_terminal_state` to match, set
     `in_progress: none`, then continue with the next check.
   - `consecutive_crashes` >= `crash_pause_threshold` -> preflight exit with Result
     `blocked (crash threshold)`. Only a human resets the counter.
3. Read-report check (this is what graduation counts). Find the newest receipt with Result
   `success`, `approval-required` or `clean no-op`. If its run number is greater than
   `report_read_through`:
   - Interactive run: ask the human "Did you read report #<N>? Anything in it wrong or useless?"
     On an explicit yes, set `report_read_through` to that run number, increment
     `manual_runs_read` in this contract's frontmatter (only while `trigger: manual`), and quote the
     answer in this run's receipt under `Report read`. Their comments are critique input for Record.
     No answer or a no: change nothing.
   - Headless/scheduled run (nobody to ask): write `Report read: confirmation pending for #<N>` in
     this run's receipt and carry on.
4. Snapshot the working tree so Verify can tell this run's writes from pre-existing changes:
   `git status --porcelain --ignored --untracked-files=all` from the repo root (if the repo is not under git, list
   modification times of the observed paths instead). Keep it in working memory, not in a file.
5. Set `in_progress: run #<N> started <ISO timestamp>`. Note the start time. From here the budget
   rule applies: at 80% of `token_budget_per_run` or `time_limit_minutes`, stop working and jump
   to step 5 of the Workflow (Record) with Result `exhausted` and a partial report.

### 1. Observe
{Numbered list of exact reads/commands. For each: working directory, command, what to extract.}
- Run observers in no-write mode. Test runners, linters and builds write caches as a side effect,
  which is an L1 scope breach: e.g. `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider`,
  `--no-cache` flags, read-only database users, `git fetch --dry-run` rather than `git fetch`.
- Compare what you see against the baseline; the report is about *changes*, not totals.
- If a source is unavailable (tool missing, auth expired, network down), record it and continue
  with the rest; if nothing could be read, the run ends `blocked (<reason>)`.

### 2. Choose
- Read `findings.md`. Every observation is either NEW (no row), CHANGED (row exists, state moved),
  or a RE-OBSERVATION (row exists, nothing moved). Only NEW and CHANGED reach the report.
- Collision check: read `acting_on` in every `{root}/*/receipts.md`. If another loop holds the
  target this run would act on, Result is `blocked (collision: <other loop>)`. At L1 `acting_on`
  stays `none`, but the read still happens every run so the protocol is proven before L2.
- Anything whose right next step is an action this contract does not permit -> it goes to the
  report's **Needs a decision** section. The Result is `approval-required` only when an open
  decision blocks this loop's own next step (it cannot usefully run again until the human answers,
  e.g. a scope change or a credential it needs). Otherwise the run is `success` with questions
  listed - an L1 report full of recommendations is the loop working, not blocked.

### 3. Act
- L1: write `REPORT.md` (overwrite, format in the receipts/report spec) and update `findings.md`:
  new row for NEW, bump `seen` + `last_seen` for RE-OBSERVATION, change `status` for CHANGED.
  Never add a second row for an existing finding.
- L2 only (after recorded graduation): {the one contracted action}. Set `acting_on: <target>`
  before, clear it after.

### 4. Verify
- Metric: `{metric_name}` = {how it is counted from this run's evidence}.
- Re-read every number the report states from its source, not from an alert or a summary that
  may have been captured mid-flight.
- Confirm the writes landed and nothing outside `writes:` changed: run
  `git status --porcelain --ignored --untracked-files=all` again and diff it against the Preflight
  snapshot. Every new or changed line must be under `{root}/{name}/`. Both flags matter: `--ignored` shows caches that
  ignore themselves (e.g. `.pytest_cache/`), and `--untracked-files=all` lists files one by one -
  without it a new file inside an already-untracked folder only shows up as that folder, unchanged.
- Scope breach found (anything else in the diff): Result `approval-required (scope breach)`. List
  the exact paths under **Needs a decision**; do not revert or delete anything yourself - the
  cleanup is another write outside scope. Put the no-write fix for the observer in the critique.

### 5. Record (always, even after a stop)
1. Prune: merge duplicate findings (keep the older row, sum `seen`), mark findings whose condition
   has cleared `resolved` with evidence, drop report items that reference things now closed.
2. Append the receipt (format in the receipts spec). Every receipt carries `tokens_consumed`
   (label estimates as estimates) and `wall_clock_minutes`.
3. Update the header: `last_run` = today's real date (read it from the system clock, never infer
   it), `last_terminal_state`, `in_progress: none`, `consecutive_crashes: 0` if this run completed.
   The header must always match the newest receipt - also after a preflight exit.
4. If `convergence_threshold` runs in a row had metric 0, add "propose slower cadence" to
   **Needs a decision**.
5. If a validator is available (`python {skill_dir}/scripts/check_loops.py --root {root}`), run it
   and fix any FAIL before ending.

## Terminal states (every run ends in exactly one)
| State | Meaning |
|-------|---------|
| `success` | Contracted work done, metric computed, report written. |
| `clean no-op` | Observed everything, nothing new or changed. Still a receipt, one line in REPORT. |
| `blocked (<reason>)` | Could not proceed: paused, crash threshold, collision, missing tool/auth. |
| `approval-required` | A human decision blocks this loop's next step (incl. `(scope breach)`). Question is in REPORT. |
| `exhausted` | Hit 80% of the token or time budget; partial report + receipt. |
| `no-progress` | Ran but produced nothing verifiable (sources unreadable, verification failed, crashed). |

No receipt = no run. A clean no-op is a result, not a reason to skip the receipt.

## Hard stops
| Type | Value | Action |
|------|-------|--------|
| token_budget | {60K}/run | at 80%: stop, partial report, Result `exhausted` |
| time_limit | {15} min | at 80%: stop, partial report, Result `exhausted` |
| crash_pause | {3} consecutive | refuse to run (`blocked (crash threshold)`) until a human resets |
| convergence | {3} runs with metric 0 | propose slower cadence in Needs a decision |
| scope | any write outside `writes:` | never; if Verify finds one, Result `approval-required (scope breach)` |

## Post-run critique
Each receipt names ONE change that would have made this run better (a wrong path, a noisy
source, a missing baseline method). Apply at most one contract change per run, and say so in
the next receipt - several simultaneous changes make it impossible to tell which one helped.
If the metric misses or the run ends `no-progress` three times in a row, stop tweaking the
prose: put a redesign question in **Needs a decision**.

## Level history
- {YYYY-MM-DD}: created at L1 (report-only).
=====
