# Manifest, proofs, independent verification, and the report

## Manifest schema (`manifest.jsonl`, append-only)

One JSON object per line. `cleanup.py log` writes these; you may write them by hand if the script is
not available, as long as the intent row is written before the action.

| Field | In | Meaning |
|---|---|---|
| `ts` | all | ISO timestamp with offset |
| `step` | all | Step number from plan.md |
| `op` | all | `move`, `archive`, `delete`, `keep` |
| `src` | all | Path relative to the root |
| `dst` | move, archive | Destination relative to the root |
| `status` | all | `intent` (before acting), `done` (after), `absent` (source already gone when the step began) |
| `tree_sha`, `files`, `bytes` | intent | Content hash and size of the source at intent time (`cleanup.py hash` format) |
| `file_shas` | intent | `{relative path inside the source: content sha}` for every file (`"."` for a single file) |
| `edited` | done | Root-relative paths inside the destination changed on purpose after the move (repointing) |
| `kind` | intent | `file` or `dir`; decides how the old path is searched for once the source is gone |
| `covered_by` | delete | Where the content still lives (a path or a URL) |
| `approved_by` | delete (if no cover) | Who approved discarding it, and when |
| `note` | any | Free text: rollback of step N, reason for an exception |

Rules: never edit or delete earlier rows; corrections are new rows with a `note`. Keep the manifest
out of the folders being moved.

Correcting a done row: if you forgot to declare a repointed file, or repointed another one after the
step was closed, append a second done row for the same step, op and src:

```
python $S log --manifest $M --step 3 --op move --src legacy/reports --dst docs/archive/reports \
    --done --edited docs/archive/reports/index.md --note "late edit: repointed index after step 5"
```

`check` takes the union of every `--edited` declaration in the manifest, so the later row corrects the
earlier one without rewriting it. Only declare edits you actually made on purpose; an unexplained
change is what `check` exists to catch.

## What `cleanup.py check` proves, and what it does not

Proves, for each completed row:
- move / archive: source gone, destination present, and every file of the source is at the
  destination with its intent-time content. Exceptions: files declared `--edited` on a done row
  (must exist, content may differ), and files a LATER logged move/delete took away. Extra files in
  the destination are ignored (a later move into it is normal). Truncation, partial copies, lost
  files and undeclared edits fail;
- delete: path gone; a local `covered_by` still holds every deleted file with the same content (it
  was also checked by `log` before the delete), or an approval is recorded;
- no intent row is left without a done row (interrupted steps surface);
- no text file under the root still mentions a moved or deleted path in any path-shaped spelling,
  including after a root variable (`"$ROOT/docs/x"`, `${workspaceFolder}/docs`, `<rootDir>/docs`) and
  inside repository web URLs (`blob/main/docs/x.md`). Not counted: files you pass with `--exclude`,
  `.cleanup/`, this skill's folder, mentions that are part of the new destination path, ignore files
  for deleted paths, and `X/docs` where `X/docs` exists under the root as a different path (a nested
  `site/docs/`).

The matcher is deliberately loud: when it cannot tell, it reports. A mention like `other-repo/docs/x`
where `other-repo/docs` does not exist here is reported even if it means another repository; read it
and either repoint it or pass the file to `--exclude` with a reason in the report. A false alarm costs
a minute; a missed reference ships a broken path.

Does not prove:
- that the project still works (run its tests and build);
- that the commit contains what the disk contains (compare `git ls-files` counts; see execution.md);
- references in binary files, files over 1 MB, or skipped folders (`node_modules`, `.git`, build
  outputs) - grep those by hand if the project stores paths in them;
- references that build a path at runtime from parts (`join(base, "reports")`) or name a top-level
  folder as an unquoted bare word (`paths: docs` in YAML); search with `refs --basename` and read the
  hits;
- a mention after a segment that happens to exist as a different path: if both `site/docs/` and root
  `docs/` exist, `site/docs/x` is treated as the nested folder even when a script meant
  `site` + root `docs` (rare; the nested folder is the likely reading);
- paths written relative to a subfolder without a dot prefix (`guide.md` from inside `docs/`, where
  the file name alone is not the moved path). Search for the file name with `refs --basename`;
- references outside the root (other repos, CI settings in a web UI, bookmarks, cron jobs). List the
  known external consumers in the plan and check each one.

Seeded failure: before trusting `check` on a real cleanup, run `scripts/selftest.py` (a throwaway
cleanup where stale references, undeclared edits, lost files, false covers, tampered covers, missing
sources and interrupted steps are each shown to fail, then pass once fixed). A check that has never
failed has not been shown to work.

## Independent verifier brief

If you can spawn a separate agent (or hand this to a human reviewer), give it only: the roots, the
plan.md rulings, the manifest, and this checklist. Do not give it your conclusions.

```
You are verifying a completed workspace cleanup. Default verdict: REJECT. Change it to ACCEPT only
if every check below passes on full evidence. Do not sample: compare every file.

1. Completeness: for every move/archive row, the destination's committed files equal the source's
   files at intent time (count and content). Report every missing or differing file.
2. Deletes: every deleted path has a cover that exists and matches, or a recorded approval.
3. Nothing unplanned: list every path added, removed or renamed in the cleanup commits; flag any
   not in the manifest.
4. References: search the roots for every old path (relative, both slash styles, absolute, bare
   name). List every hit that is not a justified historical mention.
5. Proof commands: rerun {tests / build / link check}; paste the result lines.
6. Numbers: recompute every count stated in the report from the disk; flag any mismatch and say
   what the stated number actually counted.
7. Docs: every doc that lists folders or paths matches the disk.
8. Dirty state: each repo's status is clean or contains only files that were dirty before the
   cleanup (compare with the Phase 0 record).
Return: verdict, then one line per check (PASS/FAIL + evidence), then defects in priority order.
```

When the verifier returns REJECT: fix real defects, correct wrong numbers, and re-verify. A finding
you cannot fix (something lost that cannot be recovered) is recorded as a loss, not argued away.
Findings caused by a concurrent writer are reclassified only with evidence of the other writer.

## report.md template

```markdown
# Cleanup report - {scope} - {YYYY-MM-DD}

**Terminal state**: done | partial | blocked | rolled back | no-op
**Losses**: none | {what, how it was detected, whether it can be recovered, why it cannot be
proven either way}

## What changed
| Step | Action | Commit | Proof |
|------|--------|--------|-------|

## Proofs
- Project checks: {command} -> {actual result line}
- Manifest check: {summary line from cleanup.py check}
- Commit vs disk: {counts compared}
- Independent verification: {verdict + who} | self-checked only

## Numbers (recomputed at report time, each says what it counts)
- ...

## Docs reconciled
- {file}: {what was updated}

## Deferred / needs a human
- {item} - why - who decides

## Findings worth remembering
- {surprises: locks, ignore rules, tools that pinned paths, premises that were wrong}
```

Lead with losses and decisions needed; a reader should not have to scroll to learn that something
went missing.
