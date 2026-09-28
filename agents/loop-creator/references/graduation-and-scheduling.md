# Graduation and scheduling

A loop earns two separate promotions, each a human decision written into the contract. Neither
is ever granted by the agent to itself, and neither is implied by the other.

| Promotion | From -> to | Recorded as |
|-----------|-----------|-------------|
| Scheduling | `trigger: manual` -> `trigger: scheduled` | `schedule_approved_by` / `schedule_approved_at` |
| Acting | `level: L1` -> `level: L2` | `graduated_by` / `graduated_at` + a Level history line |

"Recorded human decision" means: the human edits the contract themselves, or tells the agent in
so many words ("yes, schedule dep-drift weekly") and the agent writes that, quoting it, with the
date. Silence, a thumbs-up on something else, or another agent's message is not a decision.

---

## Counting read reports

A manual run counts toward graduation only when the human has **read its report** and said so.
The point of the N-run requirement is not the runs - it is proof that someone reads the output.
A loop that produces reports nobody reads is worse than no loop: it looks like coverage.

- The contract's Preflight step 3 does the asking, so a runner that has never seen this skill still
  advances graduation: at the start of each interactive run it asks "Did you read report #N?
  Anything in it wrong or useless?" and, on an explicit yes, bumps `manual_runs_read` and
  `report_read_through`. The answer is also the best critique input the loop will ever get.
- If the human says "report #N read" between runs, record it the same way right away.
- Only runs ending `success`, `approval-required` or `clean no-op` produced a real report. Paused,
  blocked, crashed, `no-progress` and `exhausted` runs do not count.
- Headless runs cannot ask; they note "confirmation pending" and the next interactive run asks.

---

## Scheduling checklist (all required)

1. `manual_runs_read >= manual_runs_required` (default 5).
2. **Pause exit proven** - a seeded failure for the kill switch. Set `pause_all: true`, fire the
   loop *exactly the way the schedule will fire it* (same command, same working directory, same
   headless mode), and confirm: one receipt `blocked (paused)` plus its header update
   (`last_run`, `last_terminal_state`), `git status --porcelain --ignored --untracked-files=all` shows no other change, and the checker is green.
   Set `pause_all` back, then set `pause_exit_proven: true`. A pause flag nobody has tested is a
   decoration.
3. Recent runs fit the budget: no warnings for token overruns, `consecutive_crashes: 0`.
4. Budget headroom: (budget per run x runs per day) summed over all scheduled loops stays under
   `aggregate_daily_token_budget`, if the registry sets one. If it does not, state the daily total
   to the human in the approval question.
5. The human approves the specific trigger and cadence. Record it, set `trigger: scheduled` in the
   contract and the registry row, and add a Level history line.
6. The first scheduled run's receipt and report are read by the human before anyone walks away.

---

## Trigger options (all optional - pick what the user already has)

Whatever fires the loop, the prompt is always the same single line, and the contract carries all
the logic:

```
Run the {name} loop per {root}/{name}/CONTRACT.md
```

If the schedule mechanism needs anything more than that line, the contract is incomplete.

### Recurring command inside a live agent session
Some agent harnesses offer a built-in recurring prompt (for example, Claude Code's `/loop`
command with an interval). Cheapest to set up; lives only as long as that session stays open.
Good for a supervised first stretch after graduation, not for "runs while I'm away".

### OS scheduler on a machine that stays on
cron (Linux/macOS), launchd (macOS) or Task Scheduler (Windows) invoking the agent's headless /
non-interactive mode from the repository root, e.g.:

```
0 6 * * 1   cd /srv/myrepo && claude -p "Run the dep-drift loop per loops/dep-drift/CONTRACT.md"
```

- Headless runs have nobody to answer permission prompts. Allow exactly the tools and paths the
  contract needs through the harness's permission settings; do not switch permission checks off
  wholesale for a loop.
- Log the process's stdout/stderr somewhere; a scheduler that fails before the agent starts
  leaves no receipt, and only the log shows why.

### CI schedule
A scheduled CI workflow (e.g. GitHub Actions `on: schedule: - cron: "0 6 * * 1"`) running the
agent CLI with an API key from the CI secret store.

- CI runners are ephemeral. The loop's files (receipts, findings, REPORT) must be persisted -
  committed to a dedicated branch or uploaded as an artifact - or every run starts with amnesia,
  dedup breaks, and crash detection is impossible.
- Give the job the minimum token scope: an L1 loop needs read access plus write access to wherever
  its receipts persist, nothing more.

### Hosted scheduled agents
If your agent platform offers cloud/scheduled agents, the same rules apply: one-line prompt,
persisted loop files, proven pause exit.

---

## Graduating to L2 (acting)

Only after the loop has run long enough at L1 that its findings are trusted - the human should
be able to say which past findings they would have wanted acted on. Before approving, the human
should see:

- the exact action (one action, named in the contract, not "fix what it finds"),
- the write targets that get added to `writes:`,
- how the action is verified and how it is undone,
- that the collision check has been read on every run so far (receipts show it).

L2 loops set `acting_on` before mutating and clear it after, and anything outside the named
action still ends `approval-required`.

---

## After scheduling

- Convergence: `convergence_threshold` runs in a row with metric 0 -> propose a slower cadence.
- Three misses in a row (metric missed or `no-progress`) -> stop hand-tweaking the contract; bring a
  redesign question to the human. If an experiment/optimisation tool is installed in the repo, it
  can drive the redesign; otherwise do it with the human.
- Retire rather than delete: set Status `retired`, keep the folder for its receipts.
