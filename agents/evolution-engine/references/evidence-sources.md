# Where evidence lives in an ordinary repo

Start from what already exists. Only add new logging when a parameter you need is genuinely
unrecorded - and then that logging is itself the first proposal (its "change" is to start recording;
its verdict is simply whether the data now arrives).

Every source below is optional. Use whichever the repo has; note the ones it lacks as limitations.

## Git history (almost always available)

```bash
git log --oneline --since="30 days ago" -- path/to/target      # churn on the target itself
git log --oneline --grep="revert" --grep="fix" -i --since="30 days ago"
git log --format="%h %an %s" --since="30 days ago"               # agent vs human authorship, if distinguishable
```

Signals: repeated edits to the same prompt/rule (hand-tweaking without measurement), reverts of agent
commits (`output_quality`, `override_rate`), "fix" commits landing right after agent work.

## Tests and CI

- CI run history (web UI, `gh run list` if the GitHub CLI is installed, or saved logs).
- Test files changed alongside agent commits: skip markers added, assertions loosened, tests deleted
  (`test_integrity`).
- Rerun counts and flaky-test lists (`gate_friction`, `test_integrity`).

## Agent transcripts

If the agent tool keeps session transcripts, they hold the richest data: token usage, tool calls,
retries, subagent launches, compaction events. Claude Code, for example, writes JSONL transcripts
under `~/.claude/projects/<project-folder>/`. Other tools keep their own logs; check their docs.

Useful extractions (adapt to the actual schema - inspect a few lines before trusting a field name):
- tokens / cost per session (`cost`)
- number of times the same tool call failed and was retried (`gate_friction`)
- subagent/task launches per session (`delegation`)
- compaction or context-limit events (`context_pressure`)
- final "done" claims vs what the repo shows afterwards (`faked_completeness`)

Transcripts can contain secrets and personal data. Extract numbers, not content, into proposals.

## Run receipts and logs

Loops, scheduled jobs and pipelines often write a per-run log or summary. Good receipts carry: run
id, date, terminal state (success / no-op / blocked / failed), what changed, what was verified. If
they exist, they are the natural unit of a run for measurement.

If they do not exist and the target is a recurring loop, proposing a minimal receipt (one line per
run, append-only) is usually the best first evolution.

## Hook and guard logs

Hooks that block or warn can log each firing. Counts of blocks, and how many were false alarms the
human overrode, feed `gate_friction` and `check_precision`.

## Review threads and issue trackers

PR review comments, issue reopenings and human corrections in chat are the evidence for
`override_rate`, `output_quality` and `faked_completeness`. If an issue tracker is available, a label
for "agent-caused" or "reopened" makes these countable later.

## Handoff notes

If sessions leave notes for the next one (a working-memory file, a progress doc), compare what the
note said was next with what the next session actually did first (`handoff_quality`).

## Recording the source in a proposal

Every Evidence bullet ends with `source:` and something a stranger could re-check: a file path in the
repo, a commit sha or range, a CI run id, a transcript file name, a PR number. "source: my memory of
last week" is refused by a reviewer even if the helper lets it through.
