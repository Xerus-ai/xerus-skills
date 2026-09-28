# The practicum record

One file per attempt: `{course-dir}/practicum/attempt-NN.md`. The evidence for
it goes in the sibling folder `{course-dir}/practicum/attempt-NN/`. The record
is written **before** any build work starts and filled in as the build goes.
The grader reads it, and so does the next attempt.

## Template

```
---
kind: practicum
course: {slug}
attempt: 01
title: {short name of what is being built}
mode: in-repo
target: {path, module or system being changed}
concepts: [concept-id, concept-id]
started: YYYY-MM-DD
base: {commit id at start, or none}
preexisting_changes: [paths already modified before the build, or empty]
recall_gate: passed
spec: course
grader: pending
status: building
---

# Practicum 01: {title}

## Task
What will be built, in two or three sentences. Which spec concepts it forces,
one line each. Carry-over: the "one thing to do differently" from the previous
attempt, quoted, or "first attempt".

## Acceptance criteria
- [ ] {criterion from the spec, made concrete for this target}: check: `{command}`
- [ ] ...

## Decision log
- D0 [agent] GATE ...
- D1 [human] FORK ...

## Evidence
- attempt-01/check-1.txt: first run of the acceptance check (seeded bad case)
- ...

## Grade
(pasted verbatim from the grader; nothing written here by the builder)

## Result
```

Field values:

| Field | Values |
|-------|--------|
| `mode` | `in-repo` · `patch-only` · `greenfield` (see SKILL.md) |
| `recall_gate` | `passed` (every gated lesson concept is `learning`/`retained`) · `screened` (no tutor available; the unstudied concepts passed the assessment-probe screen) · `overridden` · `no-record` (no progress file, and the human confirmed they studied) |
| `spec` | `course` · `drafted-at-practicum` |
| `grader` | `pending` · `subagent` · `fresh-process` · `human-carried` |
| `status` | `building` · `awaiting-grade` · `graded` · `abandoned` |

`base` and `preexisting_changes` are there so the diff the grader sees holds
only this build's work. At contract time, if the target is in a git repo, record
the current commit, and list any files that already have uncommitted changes.
If those files overlap the target, ask the human to commit or stash first, or
limit the grading diff to the target paths. An unrelated half-finished change
in the diff reads to the grader like part of the build.

## Writing the decision log

The decision log is the **only** evidence the orchestration rubric has. Write
it so a stranger can grade from it.

One entry per event, written **when it happens**, never reconstructed at the
end:

```
- D{n} [{who}] {TYPE}: {what happened}. {outcome}.
```

`{who}` is `human`, `agent`, or `agent-default` (the agent chose without
asking; this should be rare, and it is always logged).

| TYPE | Log it when | Feeds rubric dimension |
|------|-------------|------------------------|
| `FORK` | A design choice with real alternatives. State the options in a few words and who chose. | 1 Decomposition, 2 Verifier-first |
| `SCOPE` | The human cut, split or re-ordered the work. | 1 Decomposition |
| `CHECK` | An acceptance check was written, run, or changed. Include pass/fail and the evidence file. | 2 Verifier-first |
| `DELEGATE` | Work was handed to a subagent or parallel run, or the human decided not to. | 3 Delegation judgment |
| `CLAIM` | The agent said something was done or working. Record whether the human asked for proof, and what proof. | 4 Claim verification |
| `REDIRECT` | The human corrected the agent's direction. Quote the redirect if it is short. | 5 Course correction |
| `CONTEXT` | The human supplied a constraint, or the agent had to ask for something. | 6 Context economy |
| `DISAGREE` | The agent objected to a decision (once, with a reason), and what the human did then. | any |
| `GATE` | The recall gate's outcome: passed, screened (which concepts were probed, and the result), or no-record. This is the first entry of every log. | context for the grader |
| `OVERRIDE` | The human overrode a gate (recall gate, budget, the one-round cap). | context for the grader |

Examples:

```
- D0 [agent] GATE: progress.md shows both gated concepts retained; the 99-only concept is exempt. Passed.
- D1 [human] SCOPE: split the work into "write the failing check" then "fix the three call sites". Agent started on the check.
- D2 [human] FORK: check as a unit test vs as a lint rule; chose lint rule ("it has to fire in the editor"). Lint rule drafted.
- D3 [agent] CHECK: lint run on seeded bad file; 1 error reported (attempt-01/check-1.txt).
- D4 [agent] CLAIM: "migration complete". Human asked for the grep of remaining call sites; 1 left (attempt-01/check-2.txt).
- D5 [human] REDIRECT: "you're editing the generated client, the source is the schema file". Agent reverted and edited the schema.
- D6 [agent] CONTEXT: asked which Python version is supported; human answered 3.9.
```

Rules for the log:

- **Facts, not verdicts.** Never write "good call", "smart split", "unfortunately".
  The builder's opinion of the human is the narrative the grader must not see.
  Write what was said and what happened next.
- **Quote the human** when the exact words matter, which is usually the case
  for redirects and constraints. Keep quotes short.
- **Log the agent's own misses.** If the agent claimed "done" and was wrong, the
  CLAIM entry says so. Hiding it would bias dimension 4 upward.
- **Never back-fill silently.** If an entry is written late, mark it `(late)`.
  A thin log gives a thin grade, and that is a true finding.
- **Evidence goes in files.** Check output is saved raw under `attempt-NN/`
  and named in the entry. Never paste a paraphrase of output into the log.

## After grading

- `## Grade`: the grader's output, verbatim.
- `## Result`: two to five lines. What exists now, the artifact verdict, the
  orchestration total with the number of evidenced dimensions, the one
  behaviour to change, and, if the improvement round ran, what it fixed and
  the re-check result.
- `status: graded` (or `abandoned`, with one line in Result on why).
