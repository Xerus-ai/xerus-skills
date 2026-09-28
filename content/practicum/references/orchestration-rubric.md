# Orchestration Rubric: how well the human directed the agent

A practicum grades two things. The course's own acceptance criteria say whether
the **artifact** is any good. This rubric asks something else: **did the human
direct the agent well?** It does not depend on the course. The same six
dimensions apply whether the practicum built a lint rule, a data pipeline or a
UI component.

It exists because "I built the thing" and "I know how to get things built with
an agent" are different skills, and by default only the first gets graded.

## Evidence the grader gets

- The **decision log**: every fork where the pair picked a direction, who
  picked it, and what happened next. Agent claims, and whether anyone checked
  them, are in it too.
- The **artifact evidence**: the diff or files, plus the acceptance-check
  output.

The grader does **not** get the builder's account of how the session went.
Whoever produced the work does not grade it.

## Scale

Score each dimension 1-5. **Every score must quote or point to a specific log
entry.** A score with no citation is an impression, not a score. When the log
does not show enough, the grader marks the dimension `unevidenced` and does
not guess.

| Score | Means |
|-------|-------|
| 5 | Did this deliberately, and it changed the outcome |
| 4 | Did this consistently |
| 3 | Did this when prompted |
| 2 | Did this once, or too late to matter |
| 1 | Did not do this |
| `unevidenced` | The log does not show enough to judge |

## The six dimensions

### 1. Decomposition
Did the human split the work into steps with outcomes someone could observe, or
hand over a goal and hope? The tell is whether the agent ever had to guess what
"done" meant. **5**: the task came pre-cut into pieces the agent could finish
and the human could check.

### 2. Verifier-first
Before building, did the human insist on something that can say pass or fail?
This holds for every course. If nobody can tell whether the result is correct,
the practicum has already failed, however good the artifact looks.

### 3. Delegation judgment
Did the human hand off work that really needed its own context, and keep work
they could finish directly? Mistakes in either direction count: spawning agents
for a two-step job, and grinding by hand through something that needed a
parallel fan-out. **The question is whether each choice could be defended, not
how much was delegated.**

### 4. Claim verification
When the agent said "done", did the human check? Did they ask for the command
output, the diff, or the test that failed and then passed, or did they take the
word "done"? An agent reporting success has not proven success. This dimension
catches the most expensive habit in agentic work.

### 5. Course correction
When the agent went the wrong way, how fast did the human notice, and how
precisely did they redirect? **Speed and precision both count.** "No, not like
that" is a 2. "You're editing the generated file; the source is under src/" is
a 5. Grade the redirect, not the agent's mistake.

### 6. Context economy
Did the human give the agent what it needed without burying it? Both failures
count: holding back the one constraint that mattered, and pasting everything in
case some of it helps. The tell is the agent asking for something the human
already knew.

## Output shape

```
## Orchestration: {n}/30 ({k} dimensions evidenced)

| Dimension | Score | Evidence (log entry) |
|-----------|-------|----------------------|
| Decomposition | 4 | D{n}: "{short quote from that entry}" |
| Verifier-first | ... | ... |
| Delegation judgment | ... | ... |
| Claim verification | ... | ... |
| Course correction | ... | ... |
| Context economy | ... | ... |

**Strongest**: {dimension}: {one line}
**Weakest**: {dimension}: {one line, and the habit to change}
**One thing to do differently next practicum**: {one concrete behaviour}
```

`{n}` sums only the evidenced dimensions. Always report `{k}` next to it, so a
16/20 over four dimensions never gets read as a 16/30.

The last line is the one part that is never skipped. Six scores with nothing to
practise is a report card, not learning.

## Grading integrity

- **Never inflate.** A generous score tells the human that a habit which cost
  them an hour was fine.
- **Do not grade the agent's competence here.** If the agent was slow or wrong,
  that goes in the artifact findings, not the human's score. The one exception
  is when the human's direction caused it, and that is dimension 5.
- **`unevidenced` is a real verdict** and is better than a guess. If most
  dimensions come back unevidenced, the finding is that the decision log was
  too thin, and the grader says so plainly.
- **A dimension that never came up is `unevidenced`, not a 1.** If the agent
  never went wrong, dimension 5 had nothing to grade. A 1 means the chance came
  up and was missed.
