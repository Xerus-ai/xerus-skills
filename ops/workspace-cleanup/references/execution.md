# Executing moves and deletes safely

## Order of steps

1. **Record what has no history.** Untracked content you will touch gets committed as-is (its own
   commit, message says "record before cleanup") or, if it must not be committed, its hash goes in
   the manifest. Do this before any move.
2. **Moves before deletes.** Moving first means every delete in a later step can point at where the
   content now lives (`--covered-by`). If a cover does move after the delete, move it through its own
   logged step: `check` follows logged moves to find the cover, but an unlogged move makes the cover
   look lost.
3. **Deletes behind a gate.** Each delete has one of: a matching content hash elsewhere, a regeneration
   command that you ran, committed history that holds it, or a human's explicit approval to discard.
4. **Docs and consumers last**, but in the same session. A move whose references are not repointed is
   not finished.

## One step, end to end

```
S={this-skill-dir}/scripts/cleanup.py
M=.cleanup/2026-01-15/manifest.jsonl

python $S refs legacy/reports                                      # who points at it (incl. [inside target])
python $S log --manifest $M --step 3 --op move --src legacy/reports --dst docs/archive/reports
git mv legacy/reports docs/archive/reports                           # tracked: history follows
# ... repoint every reference found above (README.md, and index.md inside the moved tree), then:
python $S refs legacy/reports                                      # expect nothing
python $S log --manifest $M --step 3 --op move --src legacy/reports --dst docs/archive/reports --done \
    --edited docs/archive/reports/index.md                         # declare edits inside the destination
git add -- docs/archive/reports README.md                            # not the old path: git mv staged its removal
git commit -m "cleanup step 3: legacy/reports -> docs/archive/reports"
```

`check` later confirms every file of the source is at the destination with its original content,
except the files you declared with `--edited` (those must only exist). Files that arrive in the
destination later (a second move into it) are fine; files that leave it later must leave through
their own logged step, or `check` reports them missing.

Deleting a byte-identical duplicate:

```
python $S hash vendor/lib-copy vendor/lib                          # hashes must match
python $S log --manifest $M --step 5 --op delete --src vendor/lib-copy --covered-by vendor/lib
# log itself refuses if any file of vendor/lib-copy is missing from vendor/lib or differs in content.
# A cover must have the same shape: a folder covers a folder (extra files allowed), a file covers a file.
git rm -r -q vendor/lib-copy
python $S log --manifest $M --step 5 --op delete --src vendor/lib-copy --done
```

Deleting approved litter:

```
python $S log --manifest $M --step 6 --op delete --src crash.stackdump --approved-by "owner, 2026-01-15"
rm crash.stackdump
python $S log --manifest $M --step 6 --op delete --src crash.stackdump --done
```

Something the plan listed is already gone:

```
python $S log --manifest $M --step 4 --op move --src fonts --dst assets/fonts --absent
```

and tell the human in the same message. "Already absent at step 4" is a fact you can defend later;
a silent skip is not.

## Version control

- Tracked content: `git mv` (or your VCS's equivalent) so history follows. Check renames were
  detected: `git status` shows `renamed:` lines.
- Commit per step, staging only the paths the step touched. `git add -A` in a repo with other dirty
  files sweeps someone's work into your cleanup.
- Moving content between two repos: copy in, commit in the destination, verify the committed
  destination tree (not the working copy) matches the source, then remove from the source in a
  separate commit. History does not follow; say so in the commit message and point at the source
  commit.
- After each commit touching a moved tree, compare counts: `git ls-files <dst> | wc -l` against the
  file count recorded in the manifest's intent row. A shortfall usually means an ignore rule
  (`git check-ignore -v <file>` names the line). An unanchored pattern like `scripts/` matches at every
  depth; anchor it (`/scripts/`) if only the root one was meant.
- Case-only renames on case-insensitive filesystems need two moves (`a -> a.tmp -> A`).
- Never rewrite published history as part of a cleanup without explicit approval.

## Platform traps

- **Open handles block moves** (common on Windows): a running server, editor, language server or
  tool whose files live inside a folder will make renaming that folder fail. Stop the process, or
  move the folder's children one at a time. Do not force-delete to get around a lock.
- **Long paths**: deep `node_modules`-style trees can exceed path limits on Windows; move the parent,
  not each file, and check the destination file count.
- **Symlinks and junctions**: moving a link moves the link, not the target. The inventory marks them
  `kind=link`; decide for each whether the link or the target is the item.
- **Line-ending and filter conversions** can change bytes on checkout; compare committed blobs or
  hash with conversions disabled when proving identity across machines.
- **Watchers and sync clients** (cloud drives, dev servers) may recreate or lock files mid-move;
  pause them or note them in the plan.

## Bulk moves

When a step moves many items (rebucketing dozens of folders), write the mapping as data first
(a TSV of `src<TAB>dst`), review it with the human as a table, then execute it with a small script
that logs each row to the manifest before moving it and stops at the first failure. Never write a
bulk-move script whose log is written only at the end.

## Rollback

The manifest is the undo list. Walk it in reverse:

- `move` / `archive` done: move back only the files listed in the intent row's `file_shas` (files
  that arrived in the destination later, through another logged move, belong to that step and stay
  or are rolled back with it). Verify each restored file against `file_shas`, except the ones listed
  in an `edited` field: for those, either keep the edited version and repoint back, or restore the
  original from the commit before the step. Do not compare the whole tree against `tree_sha`; it
  changes as soon as anything was repointed or added.
- `delete` done with `covered_by`: restore from the covering copy or the commit before the delete.
- `delete` approved without a cover: only committed history can restore it; if it was never
  committed, it is gone, which is exactly why untracked content is recorded in step 1.
- An `intent` row with no `done` row: the step was interrupted. Inspect both `src` and `dst` before
  doing anything; either may be partial.

Append rollback actions to the manifest as their own rows (`note: "rollback of step N"`), never edit
earlier rows.
