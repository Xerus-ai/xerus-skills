# Verifying a handoff before you save it

A handoff is trusted by a reader who cannot check your memory. Every claim in it must survive the
question "how do you know?", answered with a command you ran while writing it.

## Confidence labels

| Label | Means | How to write it |
|---|---|---|
| **done** | The action happened (you did it, or saw it happen in this session). | `Rebased onto main (done).` |
| **verified** | You checked the result with a command, just now or at a stated time. | `Tests pass (verified: npm test -> 214/214, 2026-09-28 18:02).` |
| **assumed** | Not checked. Say why and what would check it. | `Staging still has the old key (assumed: no console access; check the secrets page).` |

- "Done" is not "verified". A push that ran is done; a push whose commits show up on the remote is
  verified.
- Anything reported by another agent, a subagent, another model, or an older handoff is **assumed**
  until you check it. Other agents are confidently wrong often enough to matter.
- Unlabelled state claims default to *verified*, so only leave a claim unlabelled if you checked it.

## Claim-to-command table

| Claim in the handoff | Command that backs it |
|---|---|
| Current date | `date` (POSIX shell) / `Get-Date` (PowerShell) / `python -c "import datetime; print(datetime.datetime.now().astimezone())"`; never `date` in Windows `cmd.exe` (it prompts to set the clock). Note the timezone if people or servers span several |
| Current branch, last commit, remotes, pushed or not, dirty paths, stashes | `python scripts/repo_state.py <repos...>` (add `--fetch` if the network is available) |
| Other local branches exist / track a remote / are merged | the same script's "local branches" list; `git branch --merged HEAD` |
| A branch exists only on the remote | `git branch -a -vv` (the script lists local branches only) |
| "Pushed" | `git fetch` then `git status -sb` shows no `ahead`; or `git branch -r --contains <hash>` lists the remote branch |
| "Committed" (a specific change) | `git log --oneline -- <path>` shows it; `git status --porcelain -- <path>` is empty |
| "Nothing else changed" | `git status --porcelain` is empty, or every line is explained in the state table |
| Where a remote points | `git remote -v` (a remote pointing at a public or shared URL is worth a line of its own) |
| A file exists / was deleted | `ls <path>` / `test -e <path>` |
| Tests pass | the test command, with the pass count and the date |
| A count ("230 skills", "14 open issues") | the command that counts it, re-run now; never copied from an older handoff |
| A service is running / a flag is set | the status command, health endpoint, or flag console; else mark *assumed* |
| Not a git repo / a bare repo | `git -C <path> rev-parse --is-bare-repository` fails / prints `true` (the script reports both) |

## Traps that have cost real sessions time

- **Date rollover.** Long sessions cross midnight. The date in your head is the date the session
  started. Get the date from a command and use its output for the header, the "Checked" line, and any
  "DONE" marks.
- **The handoff makes its own table stale.** Writing the handoff file and the entry-file pointer
  changes the working tree after you ran `repo_state.py`. List both in the working-tree owners, or
  re-run the script last; otherwise the resuming session reports them as unexplained drift.
- **The self-referencing hash.** A handoff cannot quote the hash of the commit that adds it. Write
  "the commit that adds this file", then check with `git log -1 --format=%h -- <handoff path>`.
- **Stale remote refs.** "N commits not pushed" is relative to the last fetch. If you cannot fetch, say
  "as of last fetch".
- **Attempted is not landed.** A push or deploy can fail after you ran it. Verify the result, not the
  invocation.
- **Rulings that changed mid-session.** "Keep everything local" in the morning, "commit locally" in the
  afternoon: carry the latest ruling and its date, and say what it replaced.
- **Numbers that drift.** A backlog count copied through three handoffs is fiction by the third. Re-run
  the count or label it *assumed (from the <date> handoff)*.
- **Untracked files with no owner.** Every untracked path either belongs to this work (pending),
  is deliberately untracked (say why: size, generated, held for a licence decision), or belongs to
  someone else (say whose, so nobody deletes it or commits it by accident).
- **State outside git.** Lock files, override markers, feature flags, running dev servers, scheduled
  jobs, credentials that were rotated. If the next session could trip over it, it gets a row.

## Pre-save checklist

- [ ] Header has an absolute written date from a date command, and names what it supersedes (or "none").
- [ ] Every ruling has a date; every "NOT approved" / "not yet" from the session is present; every
      conditional approval names its condition and who judges it.
- [ ] State table came from `repo_state.py` run in the last few minutes; every dirty path has an owner,
      including the handoff file itself and the entry-file edit.
- [ ] Every branch a ruling or next step mentions appears with its state (exists, on remote, merged).
- [ ] No state claim is unlabelled unless it was verified; every *assumed* says why.
- [ ] Next steps are numbered, and each is marked *needs the human's go* or *safe to do*.
- [ ] Every outward-facing or irreversible step is marked *needs the human's go*.
- [ ] Operational lessons are specific (symptom -> cause -> workaround), not general advice.
- [ ] Losses and never-exercised paths are listed under "Still open".
- [ ] "How to start" has a health check with its expected result.
- [ ] No secrets, tokens, or passwords; only where they live.
- [ ] 60-120 lines, or a reason it is longer.
- [ ] Old handoff has a superseded line at its top; the entry file points at the new handoff.
