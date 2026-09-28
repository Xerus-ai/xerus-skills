# Inventory signals, verdicts, homes, and the plan of record

## Reading the inventory

`cleanup.py inventory` gives you facts. These are the patterns worth a closer look, and what each
one usually means. "Usually" is the point: each is a reason to open the folder, never a verdict.

| Signal | Usually means | Check before deciding |
|---|---|---|
| `git=untracked`, large | Work nobody committed, or a download/clone dropped in | Is it someone's in-progress work? Is it a clone of a repo that exists elsewhere (`.git` inside it, a remote URL)? Record it before touching |
| `git=ignored`, holds files you did not expect | An over-broad ignore rule hiding real content | Which ignore line matches (`git check-ignore -v <path>`)? Would a clone lack it? |
| `refs=0` | Nothing points at it | Grep with `--basename` too: tools often refer to folders by bare name in config. Zero refs is a reason to ask, not to delete |
| Name contains `copy`, `old`, `backup`, `bak`, `tmp`, `v2`, `final`, a date | A stash or a snapshot | `hash` it against the thing it seems to copy. Identical: a delete candidate with proof. Different: it holds unique changes; ask |
| Same folder name in several places | Clones, vendored copies, or genuinely different things sharing a name | Hash each. Group identical ones. Different ones get renamed by owner or purpose, never merged by guess |
| `newest_mtime` long ago and `last_commit` long ago | Dormant | Dormant is not dead. Is it documented, referenced, or the only copy of something? Usually archive, not delete |
| Crash dumps, `*.stackdump`, `core`, editor swap files, `.DS_Store`, `Thumbs.db` | Litter | Safe to delete once listed; still enumerate them, never glob across the tree blindly |
| Screenshots, logs, `*.log` at repo root | Session litter | Look at dates and names; some are evidence someone wanted to keep |
| `node_modules`, `.venv`, `dist`, `build`, caches | Regenerable | Leave alone unless the task is disk space; if deleting, confirm the regeneration command works |
| A folder whose content is also inside an archive or export | Maybe covered | Does the archive capture EVERYTHING in it, or only one file type / one marker file? Partial capture means not covered |
| Docs describing folders that do not exist | Stale docs | Reconcile in Phase 7; note now so it is not forgotten |

## Verdicts by kind of thing

| Kind | Default verdict | Notes |
|---|---|---|
| Secrets, keys, certificates, `.env*` | keep, untouched | Out of scope unless the human names them. Never move them into a shared or public location |
| Another person's or tool's working area | keep | Ask the owner, not the agent who is cleaning |
| Tool-generated files that the tool rewrites (setup outputs, lockfiles, generated indexes) | keep, or regenerate | Hand edits are overwritten; change the source, rerun the generator |
| Vendored dependencies | keep | Moving them breaks builds in ways tests may not catch |
| Byte-identical duplicate | delete one, keep one | Record which copy survives as `--covered-by`. Choose the copy in the right home |
| Same-name, different-content variants | keep all, or ask | They are the history of how something evolved |
| Finished plans, old handoffs, one-off reports | archive | A dated `archive/` beside the live docs keeps them findable and out of the way |
| Docs for another project | move to their owner | Docs live with the thing they describe |
| Whole third-party repos kept for reference | keep whole, rebucket and index | Partial extraction loses the loose files people come back for |
| Empty folders | delete | Still list them in the manifest |
| Litter (dumps, swap files, stray screenshots) | delete | Enumerate; the list goes in the manifest with `--approved-by` |

## Homes

Before assigning destinations, write one line per top-level location saying what it is for:

```
HOMES
  src/            product code only
  docs/           live docs for this repo; finished ones in docs/archive/{year}/
  tools/          scripts the team runs; nothing generated
  vendor/         third-party code, untouched, one folder per upstream
  (no home)       -> anything that fits nowhere is a question for the human, not a new folder
```

Two places doing the same job is the root cause of most sprawl. The plan should end with one home
per job.

## plan.md template

```markdown
# Cleanup plan - {repo or workspace} - {YYYY-MM-DD}

Roots: {paths}. No-touch: {list}. Proof commands: {tests / build / link check, or "none exist"}.
Concurrent writers noticed: {none / list}.

## Homes
{one line per location}

## Items (everything that is not a plain keep)
| # | Path | What it is (one sentence) | Git | Refs | Verdict | Destination | Evidence | Risk |
|---|------|---------------------------|-----|------|---------|-------------|----------|------|

## Steps (executed in this order, one commit each)
| Step | Items | Action | Status |
|------|-------|--------|--------|
| 1 | untracked X | commit as-is before any move | pending |

## Questions for the human (one round)
### {topic}
- Q: {specific question}. Recommendation: {yours, with the reason}. Evidence: {hash / refs / listing}.

## Rulings ({date})
- {ruling, verbatim or close}. Overrides: {which part of the proposal, if any}.

## Deferred
- {item} - why deferred - who decides.
```

## The question round

- One round, grouped by topic, not a drip of single questions.
- Each question carries your recommendation and the evidence, so the human can answer in a word.
- Ask about premises, not just items: "the earlier plan assumes A is a duplicate of B; the hashes
  differ in 12 files. Keep both?"
- Offer the cheap safe option alongside the tidy one (archive instead of delete, index instead of
  merge).
- Record the answers in plan.md with the date. If an answer changes the plan's shape, rewrite the
  steps before executing any of them.
