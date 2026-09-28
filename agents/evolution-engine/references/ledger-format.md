# Ledger format

Everything lives in one directory, created by `evo.py init` (default `.evolution/` at the repo root;
override with `--dir` or the `EVOLUTION_DIR` environment variable):

```
.evolution/
  ledger.jsonl          append-only event log - the source of truth
  proposals/            EVO-001-short-slug.md, one per proposal
  reviews/              review-001.md, periodic snapshots
```

## ledger.jsonl

One JSON object per line. Never edit or delete a line; correct mistakes by appending a new event.
Every event has `ts` (ISO timestamp with offset), `id` (e.g. `EVO-007`) and `event`.

| event | extra fields | resulting state |
|-------|--------------|-----------------|
| `incomplete` | `path`, `target`, `title`, `variable`, `parameters_cited`, `errors[]` | `incomplete` - refused, can be fixed and proposed again |
| `proposed` | `path`, `target`, `title`, `variable`, `parameters_cited`, `min_n`, `content_hash` | `proposed` - awaiting the human gate. Re-proposing an edited file appends another `proposed` event, and the latest one wins |
| `rejected` | `by`, `reason` | `rejected` - never enacted |
| `enacted` | `approved_by`, `ref`, `frozen{min_n, baseline, gate_criteria, hash}` | `pending` - measuring; criteria frozen |
| `measurement` | `run`, `metrics{}`, `note` | still `pending`; N = number of measurement events |
| `verdict` | `verdict`, `n`, `rollback_required`, `rollback_ref`, `criteria_changed`, `reason` | `improved` / `no_change` / `reverted` |
| `rolled_back` | `ref` | same verdict; records that the required rollback was carried out |

`content_hash` is the first 16 hex chars of a SHA-256 over the whole proposal file. `enact` is refused
if the file no longer matches it, so the human approves exactly what gets enacted.

`frozen` holds the literal Baseline and Gate Criteria text (HTML comments stripped) and `min_n` as
they were at enactment. `frozen.hash` is a SHA-256 over those three. `improved`/`no_change` verdicts
are refused while the file does not reproduce that hash. `reverted` is always accepted and records
`criteria_changed: true` when the file differs or is gone. The frozen text is kept so that a proposal
edited or deleted by accident can be restored from the ledger alone.

`path` is stored relative to the directory that contains `.evolution/`. Target names are compared
case- and punctuation-insensitively (`CLAUDE.md` = `claude-md`), so name targets by repo path.

Example:

```json
{"ts": "2026-10-01T09:12:03+00:00", "id": "EVO-003", "event": "proposed", "path": ".evolution/proposals/EVO-003-cap-retries.md", "target": "hooks/review.sh", "title": "Cap reviewer retries at 2", "variable": "max_retries in the review hook", "parameters_cited": ["gate_friction", "cost"], "min_n": 5, "content_hash": "0c4e9a1f53b27d88"}
{"ts": "2026-10-01T10:40:55+00:00", "id": "EVO-003", "event": "enacted", "approved_by": "sam", "ref": "4f2a9c1", "frozen": {"min_n": 5, "baseline": "gate_friction: mean 3.1 retries/run ...", "gate_criteria": "- improved: mean retries <= 2.0 ...", "hash": "9b1e0c77d2a4f310"}}
{"ts": "2026-10-02T16:05:10+00:00", "id": "EVO-003", "event": "measurement", "run": "pr-231", "metrics": {"retries": 1.0, "cost_usd": 0.42}, "note": ""}
```

## Restoring a lost or edited proposal

This applies when an enacted (`pending`) proposal file was deleted or edited, and `verdict improved`
or `verdict no_change` is refused because the file no longer matches the frozen criteria.
(`verdict reverted` never needs this, because it is always accepted.)

1. **From version control, if the file was committed** (recommended):
   `git log --oneline -- <path>`, then `git checkout <sha> -- <path>` using the commit that matches
   the enactment. Take `<path>` from the `proposed` event (`evo.py show EVO-007`).
2. **From the ledger alone, if git cannot help**: run `evo.py show EVO-007` and find the `enacted`
   line. Its `frozen` object holds everything the verdict is judged against. Recreate the file at the
   `path` from the `proposed` event with at least:
   - frontmatter `min_n:` set to `frozen.min_n`;
   - a `## Baseline` section whose body is `frozen.baseline`, verbatim;
   - a `## Gate Criteria` section whose body is `frozen.gate_criteria`, verbatim.

   Rebuild the other fields and sections (id, target, Evidence, Change...) from the `proposed` event
   and your notes. They are not part of the frozen hash. Add a line under the title saying the file
   was restored from the ledger and when. A refused verdict also prints the frozen text, so you can
   copy it from there.
3. **Re-run the verdict.** If it is still refused, the restored text differs from the frozen text.
   Usually this is whitespace inside a line or a changed bullet. Leading and trailing blank lines and
   HTML comments are ignored.

Never "restore" criteria you would prefer to the frozen ones. If they turned out to be wrong,
record `reverted` and write a new proposal.

## Proposal file

`evo.py new` writes this template. HTML comments are guidance and are ignored by the checks, so an
unfilled template fails.

```markdown
---
id: EVO-003
target: hooks/review.sh
title: Cap reviewer retries at 2
date: 2026-10-01
variable: max_retries in the review hook
parameters_cited: gate_friction, cost
min_n: 5
---

# EVO-003: Cap reviewer retries at 2

## Evidence
- [gate_friction] 8 of the last 12 runs hit 3+ review retries; 5 of those retries repeated an identical finding - source: CI runs 1180-1191
- [cost] runs with 3+ retries averaged 2.4x the tokens of runs with <= 1 - source: transcripts for the same 12 runs

## Baseline
gate_friction: mean 3.1 retries/run (N=12, 2026-09-10..2026-09-30). cost: mean 0.71 USD/run (same window).

## Hypothesis
Retries past the second repeat the same finding (confirmed by reading all 5 cases); the agent loops
rather than escalating. Capping at 2 and escalating to the human should cut retries and cost without
letting more defects through.

## Gate Criteria
- improved: mean retries <= 2.0 AND mean cost <= 0.55 USD over 5 runs, no escaped defect traced to these runs
- no_change: mean retries above 2.0 or mean cost above 0.55 USD (but cost not above 0.71), no escaped defect
- reverted: any escaped defect traced to a run that hit the cap, OR mean cost above 0.71 USD

## Change
`hooks/review.sh`: `MAX_RETRIES=5` -> `MAX_RETRIES=2`; on hitting the cap, print the last finding and exit non-zero.

## Rollback
`git revert <sha of the enactment commit>`
```

Required by the checker:
- Frontmatter: `id`, `target`, `title`, `variable`, `parameters_cited`, and `min_n` (an integer >= 3).
- `parameters_cited`: each entry is one of the ten keys in `parameters.md`, or `custom:<name>`, where
  `<name>` appears in the Evidence section (define it in a paragraph there).
- Non-empty sections: Evidence, Baseline, Hypothesis, Gate Criteria, Change, Rollback.
- Evidence: every bullet has a number before its `source:`, and the source is checkable. It must
  contain a digit, a `/`, a `#` or a file name. "source: my gut" fails.
- Baseline: contains a number.
- Gate Criteria: filled `- improved:`, `- no_change:` and `- reverted:` lines, each with a threshold
  number.
- `variable`: names a single thing (no commas or semicolons).

## Review file

`.evolution/reviews/review-NNN.md`:

```markdown
# Evolution review NNN - YYYY-MM-DD

## Scope
Targets covered, window, unit of a run, total N.

## Parameters
| target | parameter | value | N | vs previous review | confidence |

## Evolutions
- Closed since last review: id, verdict, one line of why.
- Pending: id, runs measured / min_n, early signal (no claims).
- Retroactively logged: changes shipped outside the cycle, now entered as enacted and pending.

## What improved / what did not / what cannot be measured yet

## New proposals suggested by the data
One line each, with the parameter and the data point that motivates it.
```
