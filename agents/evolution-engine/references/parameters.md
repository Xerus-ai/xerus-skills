# The ten parameters

A proposal cites one or more of these by their key (the left column) in `parameters_cited`. Assess as
many as the evidence supports; for each, state the value, N, and the window. "Not measurable yet" is
a valid entry - it tells you what to start recording.

| # | Key | What it measures | Typical evidence | Direction |
|---|-----|------------------|------------------|-----------|
| 1 | `cost` | Tokens, money and wall-clock time per run | Transcript token usage, billing export, run start/end timestamps | Lower, at equal quality |
| 2 | `gate_friction` | How often a run fails a gate (test, lint, hook, review) and how many attempts it takes to pass | CI history, hook logs, retry counts in transcripts | Fewer failed gates and attempts - *without* the gate getting weaker |
| 3 | `override_rate` | How often the human rejects, rewrites or ignores what the agent suggested | PR review threads, "revert"/"undo" commits, human edits right after agent edits | Lower |
| 4 | `handoff_quality` | Whether the next session/run picks up where the last left off, or re-derives and repeats work | Handoff/notes files vs what the next session actually did first | More continuation, less rediscovery |
| 5 | `test_integrity` | Tests passing for the right reason: no skipped/disabled tests, no assertions weakened to go green, no flakes | Test diffs, skip markers added, CI rerun counts | Fewer weakened or flaky tests |
| 6 | `faked_completeness` | Claims of "done/fixed/shipped" that were not true (no commit, test not run, feature not wired) | Human corrections, reopened issues, receipts contradicted by the repo state | Zero; any occurrence is significant |
| 7 | `output_quality` | Longitudinal quality of what the agent produces | Review cycles per PR, bugs traced back to agent changes, reverts of agent commits | Fewer cycles, fewer later bugs |
| 8 | `delegation` | Outcomes when work is split across subagents vs done solo | Subagent counts in transcripts, per-mode cost and defect rate | Whichever mode wins on the other parameters for this task type |
| 9 | `context_pressure` | How close runs get to the context limit, and how often they compact or lose the thread | Peak context size, compaction events, "as I mentioned earlier" errors | Lower peak, fewer compactions |
| 10 | `check_precision` | Precision of reviewers/checkers/guards: real problems vs false alarms, and misses found later | Findings dismissed by the human vs acted on; bugs a check should have caught | Fewer false positives AND no rise in misses |

## Computing them honestly

- **Define the unit of a run first.** A session, a pipeline execution, a PR, a scheduled loop tick.
  Baseline and measurements must use the same unit.
- **Rates need denominators.** "4 faked completions" means nothing without "out of 30 runs".
- **Pair efficiency with quality.** `cost` or `gate_friction` improving while `output_quality` or
  `test_integrity` drops is a regression wearing a disguise. When citing an efficiency parameter,
  name the quality parameter you will watch alongside it in the `reverted:` criterion.
- **`check_precision` has two sides.** Silencing a noisy check raises precision and may lower
  recall. Any change to a check must say how misses will be noticed.
- **Zero-tolerance parameters.** For `faked_completeness`, one new occurrence after the change can
  justify `reverted` regardless of averages - say so in the gate criteria up front.

## Custom parameters

If none of the ten fits, cite `custom:<name>` and define it in a paragraph (not a bullet) inside the
proposal's Evidence section, using the name verbatim:
what it counts, the unit of a run, where the number comes from, and which direction is better. If
the same custom parameter shows up in three proposals, it has earned a row in your own copy of this
table.
