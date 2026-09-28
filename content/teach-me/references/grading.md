# Grading

The tutor who explained an idea is the worst judge of whether the learner got it: it knows what
the learner *meant*, it wants the lesson to have worked, and it has already heard half the
answer in the conversation. So grading is kept separate from tutoring - structurally when the
host allows it, procedurally when it does not.

## What gets graded

One answer to one question about one concept. The grade is one of:

| Grade | Rule |
|---|---|
| `recalled` | every **applicable** `must_include` point is shown |
| `partial` | at least one applicable point shown, at least one missing |
| `missed` | no applicable point shown, or the answer rests on a misconception that undoes the idea |

- **Applicable points.** A varied question (see `questioning.md`) may not ask for every
  `must_include` point. A point the question actually asked never requested is `n/a` - it is
  neither shown nor missing. At least one point must be applicable, or the question did not test
  the concept; ask a better one instead of grading.
- **Grade the idea, not the words.** A short answer in the learner's own words that shows the
  idea earns the point. Exact terms and complete lists are not required unless the term itself
  is the idea.
- **Never inflate.** Effort, a good conversation or a near-miss is not `recalled`. Never answer
  for the learner, never fill a gap in their answer with what they "obviously meant".

## Path A - a separate blind grader (use this when the host can run subagents)

Spawn a fresh subagent for each answer (or one per batch of answers from the same review). Give
it **only** the brief below, filled in. It must never see the tutoring conversation, the lesson
text, the tutor's opinion, or other answers' grades.

```
You are grading one learner answer. You have not seen the lesson or the conversation, and you
must not guess at what the learner meant beyond what they wrote.

Concept: {concept-id}
Question asked: {the question exactly as the learner saw it, including any code}
Rubric - an answer should show each point the question actually asks for:
{must_include points, one per line}
Known misconceptions (wrong belief -> why it is wrong):
{misconceptions lines, or "none listed"}
Learner answer (verbatim):
{answer}

Rules:
- For each rubric point decide: shown | missing | n/a (n/a only if this question never asked
  for it). Quote the words in the answer that show it.
- Credit the idea in any wording; do not require exact terms.
- grade = recalled if every applicable point is shown; partial if some are; missed if none are
  or the answer rests on a listed (or equally serious) misconception.
- If a rubric point could not be earned by ANY good answer to this question, report it as
  rubric_gap rather than marking it missing.

Reply with JSON only:
{"concept": "...", "grade": "recalled|partial|missed",
 "points": [{"point": "...", "verdict": "shown|missing|n/a", "evidence": "..."}],
 "misconception": "the wrong belief shown, or null",
 "rubric_gap": "description, or null",
 "feedback": "one or two sentences on the idea, for the learner"}
```

Check the reply names the same concept you sent. If the JSON is malformed or the concept is
wrong, ask once more; never record a grade you had to reconstruct yourself.

## Path B - inline grading (no subagents)

Grade before you react. In this order, with nothing evaluative said to the learner first:

1. Write out the applicable `must_include` points.
2. For each, quote the part of the answer that shows it, or write `missing` / `n/a`.
3. Check the answer against the listed misconceptions.
4. Apply the grade rule mechanically from steps 2-3.
5. Only now tell the learner the grade and explain.

Show steps 1-4 to the learner - it keeps the grade honest and teaches them what a complete
answer contains. Mark the log entry `grader: inline` so the record says how it was graded.

## After the grade

1. Record it: `python scripts/progress.py grade COURSE_DIR CONCEPT GRADE` (or by hand per
   `progress-format.md`). If the script reports PRACTICE, the concept was already graded today:
   the schedule does not move.
2. Tell the learner the grade and the feedback. For `partial` / `missed`, re-teach the missing
   point from the lesson - a different angle than the first time, often the worked example or a
   common mistake - then move on. Do not re-ask the same question immediately for a new grade;
   the next review does that.
3. Note in the session log: the concept, the grade, any misconception shown, and (if asked) the
   learner's confidence.

## Defective rubrics

If the grader reports a `rubric_gap`, or a `must_include` point is plainly something the probe
never asks for, the rubric is wrong, not the learner. Test it first: read the probe alone,
answer it as a good learner would, mark that answer against the rubric. Only a point that good
answer would never contain is a defect - a checker tripping on a word is not.

For a real defect: grade the answer on the remaining points, tell the learner, and draft a fix
for that one `assessment.md` entry (probe and/or `must_include`). Apply it only after the
learner explicitly approves, never change the concept id, and log the change.
