# Blind grading

The builder never grades, and the grader never builds. This file covers how to
get a grade from something that did not watch the session, in whatever
environment the skill is running in.

## What "blind" means here

The grader sees **only** the grading bundle:

1. The course's practicum spec: concepts under test, acceptance criteria, and
   anti-tasks. This is the artifact rubric.
2. The course's key lessons or principles, if the spec cites specific ones and
   they are short. Skip whole lesson files when the spec's criteria are
   enough; the grader is judging the build, not re-taking the course.
3. `orchestration-rubric.md` from this skill.
4. The practicum record's **Task**, **Acceptance criteria** and **Decision
   log** sections, exactly as written during the build.
5. The artifact evidence: the diff (or a file list plus contents for
   greenfield work), and the acceptance-check output **as captured**, not
   summarised.

It does **not** see the conversation, the builder's summary of how things went,
the Result section, or any "notes to the grader". Anything the builder writes
*after* the build and hands to the grader counts as narrative and stays out.
That is why the decision log has to be written as the build happens (see
`practicum-record.md`).

`scripts/grade_bundle.py` assembles the bundle from exactly those inputs, so
the blindness is mechanical. You can open the file and check what the grader
saw. Prefer it over assembling the bundle by hand.

## Pick a grader (feature-detect, in this order)

### Tier 1: a subagent (preferred)

If the environment can spawn a subagent with a fresh context (a Task / Agent
tool or equivalent), spawn **one** grader. Give it the grader prompt below plus
the path to the bundle file, and nothing else. Do not add a sentence of your
own framing ("the human did really well on..."). That sentence is exactly the
leak this step exists to prevent.

If the subagent can read files, point it at the bundle and forbid it from
reading anything else in the repo except files the diff names. If it cannot
read files, paste the bundle contents in as the whole message.

### Tier 2: a fresh process

If no subagent tool exists but an agent CLI is installed that can run one
headless prompt in a new process (check with `command -v` or `where`; for
example `claude -p`), pipe the grader prompt and the bundle to it through
stdin, and capture stdout into the practicum record. A fresh process has none
of this session's context, which is the property that matters.

Show the human the exact command before running it. It is a new model call,
and the human may want to pick the model.

### Tier 3: human-carried (always available)

If neither is available, **do not grade**. Write the bundle file, then tell the
human:

> The grade has to come from something that did not watch this build. Open a
> new session (any capable model, no shared history), paste the contents of
> `{bundle path}`, and paste the reply back here.

Set the record's `status: awaiting-grade` and stop there. When the reply comes
back, paste it into the record verbatim under **Grade** and continue with the
improvement round.

A "grade" the builder writes itself, even labelled "provisional" or
"self-assessment", is not a fallback. It is the failure this skill exists to
prevent. If the human asks "so how did I do?" before a grade exists, the answer
is "it has not been graded yet", plus the tier-3 instructions.

## Grader prompt

Use this text verbatim as the grader's instructions. Put the bundle after it.

```
You are grading a practicum: a learner built something real, pairing with an
AI agent, to prove a course's material is usable. You did not watch the
session. You have only the bundle below. Grade from its evidence and nothing
else.

Posture: skeptical. The work is unproven until the evidence proves it. Every
finding must point at something concrete in the bundle (a diff hunk, a line of
check output, a decision-log entry). A concern you cannot point at is not a
finding.

Produce exactly two sections.

## Artifact
For each acceptance criterion in the practicum spec, one row: criterion,
verdict (met / not met / unverified), evidence. "unverified" is required
whenever the check output is missing, truncated, or does not actually
exercise the criterion. Never infer that a check passed because the log says
someone ran it; the output must be in the bundle. Then list any anti-task the
build drifted into. Then list findings, each marked BLOCKING (the artifact is
wrong or does not meet a criterion) or MINOR (worth fixing, does not change
the verdict). End with one line: overall artifact verdict (pass / partial /
fail / unverified) and why.

## Orchestration
Apply the orchestration rubric in the bundle exactly: six dimensions, 1-5 or
"unevidenced", every score citing a decision-log entry by its ID. Follow the
rubric's output shape, including the "one thing to do differently next
practicum" line, which you must not skip.

Rules: do not fix anything, do not suggest rewrites longer than one line per
finding, do not grade the agent's skill as if it were the learner's. Do not
be generous. A kind grade teaches the wrong lesson.
```

## After the grade

- Paste the grader's output into the record verbatim. Do not paraphrase it,
  soften it, or reorder findings.
- If the builder disagrees with a finding, write the disagreement **under**
  the grade as a separate, labelled note. The grade itself stays as the grader
  wrote it.
- For the improvement round, fix BLOCKING findings first, re-run the
  acceptance check, and append the new output. The round is **not** re-graded
  on orchestration; the log for that round is short and the first grade is
  the reading that counts. If the environment allows it cheaply, the artifact
  section may be re-graded by a fresh grader on the updated evidence. Record
  which one you did.
