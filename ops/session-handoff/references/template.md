# Handoff template

Copy everything between the rules into a new file (default `docs/handoffs/YYYY-MM-DD-<slug>.md`) and
replace every `<...>`. Delete guidance lines (the ones starting with `>`) as you fill them. Target
length: 60-120 lines.

---

# Handoff: <the point you are handing off from, e.g. "after the auth migration, before cutover">

**Written**: <YYYY-MM-DD>, end of <session name or number, if the project numbers sessions>.
**Supersedes**: `<path of previous handoff>` (kept for history) | none.
**Read first**: <1-2 pointers: a log entry, a receipt, a plan section. Omit if the handoff stands alone.>

## Human rulings in force

> Near-verbatim, dated, scoped. Put the negatives first: they are what a fresh agent is most likely to
> violate. Carry older rulings that still hold and say so. Mark a ruling that was overturned as such
> rather than silently dropping it if the old one is still visible elsewhere.

- **<Ruling in bold>** (<YYYY-MM-DD>). <One line of scope: which repos / steps it covers.>
- **NOT approved: <action>.** Human said "<their words>" on <YYYY-MM-DD>. Ask again <when / after what>.
- **Approved once <condition>: <action>** (<YYYY-MM-DD>). Who judges the condition: <the human /
  a stated check>. Until then it is *needs go*. (Deleting a remote branch is a push.)
- **Decided: <question>** -> <answer> (<YYYY-MM-DD>). Do not reopen.
- **Open, human's call**: <question> (<since YYYY-MM-DD>). <Your recommendation in one line, if any.>

## State you inherit

> Paste the table from `scripts/repo_state.py`, then edit the last column so every dirty or untracked
> path has an owner: yours and pending, deliberately untracked (why), or not yours (whose). Add a row
> for anything that is not a repo but still matters: lock or override files, feature flags, running
> servers, scheduled jobs, a remote that points somewhere dangerous.

Checked <YYYY-MM-DD HH:MM> with `repo_state.py` (verified unless marked).

| Repo | Branch | Last commit | Remote | Pushed? | Working tree |
|---|---|---|---|---|---|
| `<path>` | <branch> | `<hash>` <subject> | <name -> url> / none | <in sync / N not pushed / no remote> | clean / <N untracked: what and why> |
| <non-repo item> | - | - | - | - | <e.g. "lock file `tmp/deploy.lock` present; human removes it after cutover"> |

## What this session did

> One line each, in the order done. Link the commit or log for detail. Mark each done / verified.

- <Thing> (<commit hash>; verified: <command -> result>).
- <Thing> (done; not verified because <reason>).

## Next, in order

> Numbered. Each item says whether it **needs the human's go** or is **safe to do**. Where there is a
> choice, give your recommendation, not a menu. When an item is finished later, strike it through in
> place with the date rather than deleting it.

1. **<Step>**: <one or two lines: what, where, done-when>. *Needs the human's go* (<why: outward /
   irreversible / cost>).
2. **<Step>**: <...>. *Safe to do.*
3. ~~**<Step finished after this was written>**~~ **DONE <YYYY-MM-DD>**: <one line, verified how>.

## Method (reuse, do not reinvent)

> Recipes that worked this session, as exact commands or pointers to scripts / briefs in the repo. Only
> what the next session will actually repeat.

1. <Step of the recipe>: `<command>`.
2. <...>

## Operational lessons (these cost time)

> Only lessons that cost real time. One line each: symptom -> cause -> workaround.

- **<Short name>**: <symptom> -> <cause>. Do <workaround> instead.

## Still open

> Unresolved decisions (if not already under rulings), known gaps, paths never exercised against the
> real thing, and any losses, with what is and isn't known about them.

- <Item> (<since YYYY-MM-DD>).

## How to start next session

1. `<health-check command>`: expect <result>.
2. `python <path to repo_state.py> <repos>`: compare with the table above; report differences.
3. Ask the human: <the one question that unblocks the next step>.
4. Then: <first concrete step>.

---

## Worked example (fictional)

```markdown
# Handoff: after the billing-service extraction, before the traffic switch

**Written**: 2026-03-14, end of session 12.
**Supersedes**: `docs/handoffs/2026-03-11-mid-extraction.md` (kept for history).
**Read first**: the 2026-03-14 entry in `docs/changelog.md`.

## Human rulings in force

- **NOT approved: switching production traffic.** "Not until finance signs off" (2026-03-14).
- **Nothing is pushed.** Commits are local in both repos; every push needs the human's go (2026-03-12).
- **Decided: keep the legacy endpoint for 30 days after the switch** (2026-03-11). Do not reopen.
- **Open, human's call**: delete the `billing_v1` tables now or after the 30 days (since 2026-03-13).
  Recommendation: after; the rollback path needs them.

## State you inherit

Checked 2026-03-14 18:40 with repo_state.py (verified unless marked).

| Repo | Branch | Last commit | Remote | Pushed? | Working tree |
|---|---|---|---|---|---|
| `api` | extract-billing | `4be21c0` Route billing calls through client | origin -> github.com/acme/api | 5 commits NOT pushed | clean |
| `billing-service` | main | `91d0a7e` Add idempotency keys | none | no remote | 1 untracked: `load-test/results/` (deliberate, 200 MB) |
| staging flag | - | - | - | - | `BILLING_SPLIT=on` in staging only (verified in the flag console) |

## What this session did

- Extracted invoice + refund handlers into billing-service (`91d0a7e`; verified: 212 tests pass).
- Switched `api` to the client behind `BILLING_SPLIT` (`4be21c0`; verified on staging).
- Load test at 2x peak: p99 180 ms (done; the run was on staging data only, not production-shaped).

## Next, in order

1. **Create the billing-service remote and push both repos.** *Needs the human's go* (outward).
2. **Production-shaped load test** with the anonymised snapshot. *Safe to do.*
3. **Switch production traffic.** *Needs the human's go* and finance sign-off (ruling above).

## Operational lessons (these cost time)

- **Test DB port clash**: tests hang at setup -> a second local database on the same port. Stop it or
  set `TEST_DB_PORT` before running.

## How to start next session

1. `make test` in both repos: expect all green.
2. `python .claude/skills/session-handoff/scripts/repo_state.py api billing-service`: compare with the table.
3. Ask the human: "Remote and push for both repos (step 1): go?"
```
