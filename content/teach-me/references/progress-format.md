# progress.md - the learner's record

One file per course, at `{course}/progress.md`. teach-me creates it on the first graded answer or
first log entry. It follows the shared shape of course format 1 (so a practicum runner reads the
same file) plus one teach-me section, `## Review schedule`.

`scripts/progress.py` does every write below. The rules are spelled out here so they can be
applied by hand when Python is not available - by hand, follow them exactly; do not improvise
intervals.

## Shape

```
---
kind: progress
course: spaced-repetition
started: 2026-09-28
updated: 2026-10-01
lessons_completed: 1
practicum: not-started
---

# Progress — Spaced Repetition, From First Principles

## Concept status

- forgetting-curve: retained (last: 2026-10-01)
- decay-rate: lapsed (last: 2026-09-30)
- retrieval-practice: learning (last: 2026-09-30)

## Review schedule

- forgetting-curve: box 2, due 2026-10-06
- decay-rate: box 0, due 2026-10-01
- retrieval-practice: box 0, due 2026-10-01

## Log

### 2026-09-30 — tutoring
- Taught lesson 01; both concepts checked at the end of the lesson.
- decay-rate: answer treated review as optional; re-explained with the worked example.
```

- **Frontmatter.** `updated` = date of the last write. `lessons_completed` is recomputed, never
  incremented by hand. `practicum` belongs to the practicum runner: teach-me writes
  `not-started` when it creates the file and never changes it afterwards.
- **Concept status** is current state, rewritten in place. `last` = date of the last
  *scheduled* grade. A concept not listed is `new`.
- **Review schedule** is current state, rewritten in place.
- **Log** is append-only history, newest last, absolute dates. teach-me's entries are headed
  `### YYYY-MM-DD — tutoring` (a practicum runner writes `— practicum`; those are the only two
  labels the shared format allows). Never edit or delete a past entry.
- Any other `##` section (a practicum runner may add its own) is preserved untouched.

## Statuses

| Status | Meaning |
|---|---|
| `new` | never graded |
| `learning` | graded, never yet recalled in full |
| `retained` | the last scheduled grade was `recalled` (or `partial` while already retained) |
| `lapsed` | was recalled once, then `missed` - it has been forgotten and must be relearned |

## Grades and the schedule (a simple Leitner box system)

A grade is one of `recalled` (every applicable rubric point shown), `partial` (some) or `missed`
(none, or a misconception that undoes the idea) - see `grading.md`.

Interval after landing in a box: box 0 = 1 day, 1 = 2 days, 2 = 5, 3 = 12, 4 = 30, 5 = 75,
6 = 180 (the ceiling).

| Grade | Box | Next review | Status |
|---|---|---|---|
| `recalled` | +1 (max 6) | interval of the new box | `retained` |
| `partial` | unchanged | half the current box's interval, at least 1 day | `learning` if it was `new`, otherwise unchanged |
| `missed` | back to 0 | 1 day | `lapsed` if it was ever recalled, otherwise `learning` |

**One scheduled grade per concept per day.** If a concept already has a grade dated today, a
second attempt is *practice*: log it, but it does not move the box, the due date or the status.
This keeps same-day re-drilling from faking long-term retention, and makes a repeated or retried
grade call harmless.

**A review is due** when its due date is today or earlier. Most overdue first.

## lessons_completed

The number of lessons `01..NN` whose concepts (from the index concept map) are **all**
`retained` right now. The `99` line never counts. It can go down when a concept lapses - that is
honest, and the next review brings it back.

## Script reference

```
python scripts/progress.py status COURSE_DIR            # where the learner is, what is due
python scripts/progress.py due COURSE_DIR               # due concepts, most overdue first
python scripts/progress.py item COURSE_DIR CONCEPT      # that concept's assessment entry
python scripts/progress.py grade COURSE_DIR CONCEPT recalled|partial|missed
python scripts/progress.py log COURSE_DIR --file entry.md
python scripts/progress.py draw                         # random question type 1-7
```

Paths are relative to wherever the skill is installed (e.g. `.claude/skills/teach-me/scripts/`).
`--today YYYY-MM-DD` overrides the date for testing. Log text goes in a file, never on the
command line - real answers break shell quoting.
