# Course folder format (format 1)

This file is the contract between **course-builder** (which writes courses) and the skills
that read them: a tutor (e.g. `teach-me`), a practical-task runner (e.g. `practicum`), and
anything else that wants to find, quiz on, or track progress through a course. If you
consume courses, code against this file, not against whatever a course happens to look like.

`scripts/check_course.py <course-dir>` validates a folder against everything marked
**required** below. A course that fails the check is not finished. A complete, passing example
lives in `examples/spaced-repetition/`.

---

## 1. Where courses live

- **Default root:** `courses/` at the root of the user's repository. One sub-folder per
  course: `courses/{slug}/`.
- **Override:** the user may name any other root (e.g. `docs/learning/`). Respect it for the
  whole build. If the repo already contains courses somewhere else, write the new one next to
  them rather than starting a second root.
- **Finding courses (consumers):** in this order, stop at the first that yields results:
  1. a path the user gave explicitly;
  2. `courses/*/index.md`;
  3. any `index.md` in the repo whose frontmatter has `kind: course` (skip `.git/`,
     `node_modules/`, virtualenvs, build output).

  A course is identified by its `slug` (from the index frontmatter), not by its folder name,
  though the two are equal when course-builder made it.

## 2. Folder layout

```
{root}/{slug}/
  index.md              REQUIRED  course map: frontmatter + objectives + lessons + concept map
  01-{lesson-slug}.md   REQUIRED  lessons, numbered 01..NN, contiguous, no gaps
  02-{lesson-slug}.md
  ...
  assessment.md         REQUIRED  tutor-facing probes + rubrics, one entry per concept
  99-practicum.md       REQUIRED  practicum spec (what a practical task must prove)
  course.html           optional  compiled single-file reading version (generated)
  sources/              optional  captured source text (cleaned transcripts, notes)
  progress.md           RESERVED  learner progress; written by the tutor / practicum, never by
                                  course-builder (see section 8)
  practicum/            RESERVED  practicum attempt records (attempt-NN.md + attempt-NN/ evidence);
                                  owned by the practicum runner, never by course-builder
```

Validators and readers must tolerate reserved entries and ignore any other sub-folder they do
not own.

Naming rules:

- `slug`: lowercase `a-z`, `0-9`, `-`; starts with a letter; at most 48 characters.
- Lesson files: two-digit number, a hyphen, a lesson slug with the same character rules, `.md`.
  Numbers run `01` to `NN` with no gaps. `00` and `99` are never lessons (`99` is the
  practicum). A course has at least 2 and at most 12 lessons; 4-8 is the normal range.
- All links between course files are plain relative Markdown links to siblings,
  e.g. `[Retrieval practice](02-retrieval-practice.md)`, so the course reads correctly on any
  Markdown renderer. No wikilinks, no links that leave the course folder.

## 3. Frontmatter subset (all course files)

Every course file starts with a `---` fenced frontmatter block. To keep it parseable without a
YAML library, only three shapes are allowed:

```
key: scalar value
key: [item-one, item-two]
key:
  - item one
  - item two
```

No nesting beyond that, no multi-line scalars. Dates are `YYYY-MM-DD`. Quotes around scalars are
optional and stripped by readers.

## 4. `index.md` (the course map)

Frontmatter (all keys required unless marked):

```
---
kind: course
format: 1
slug: spaced-repetition
title: Spaced Repetition, From First Principles
summary: One sentence saying what the learner will be able to do afterwards.
level: intro                # intro | intermediate | advanced
created: 2026-09-28
updated: 2026-09-28
lessons: 5                  # number of lesson files, 01..05
assessment: assessment.md
practicum: 99-practicum.md
sources:
  - https://www.youtube.com/watch?v=VIDEO_ID
  - notes/memory-research.md
  - model-knowledge
engram_topic: none          # optional: none | pending-install | {engram topic id}
---
```

(Comments after `#` are shown for explanation only; do not write them in real files.)

`sources` lists only material that was actually read during the build: URLs, repo-relative
paths, or the literal `model-knowledge` when a lesson was written from general knowledge
rather than a source. Never invent a citation.

Body — these `##` headings, in this order:

1. `# {title}`
2. `## About this course` — a short paragraph: who it is for, what it covers, what it does not.
3. `## Learning objectives` — one line per objective with a stable id:
   `- O1: Explain why retrieval beats re-reading for long-term retention.`
   Objectives are observable ("explain", "build", "diagnose", "choose between"), never
   "understand" or "know about".
4. `## Prerequisites` — bullet list, or the single line `- None.`
5. `## Lessons` — numbered list, one per lesson, linking the file and giving its one-line goal:
   `1. [The forgetting curve](01-the-forgetting-curve.md) — why memories decay and how fast.`
6. `## Concept map` — **the line grammar consumers parse**:
   ```
   - 01: forgetting-curve, decay-rate
   - 02: retrieval-practice, desirable-difficulty
   - 03: spacing-effect
   ```
   One line per lesson, in lesson order, `- NN: ` then comma-separated concept ids. Every
   concept id in the course appears in **exactly one** lesson — the one that teaches it most
   directly (decide by reading the lesson, not the title). An optional final `- 99: ...` line
   may list concepts only the practicum exercises; `99` is never counted as a lesson.
7. `## Concept dependencies` (optional) — `- spacing-effect <- forgetting-curve, retrieval-practice`
   (left concept builds on the right ones). Tutors use it to decide what to re-teach first
   when a learner stalls.
8. `## Practicum` — one line linking `99-practicum.md`.
9. `## Provenance` — which lessons came from which sources, which sources were reused from an
   earlier extraction vs freshly extracted, and anything that shipped short (a video with no
   transcript, a doc that could not be read). Honest gaps here, not padding in the lessons.

Concept ids: lowercase kebab-case, unique within the course, stable forever once a
`progress.md` exists (see section 9).

## 5. Lesson files `NN-{lesson-slug}.md`

Frontmatter:

```
---
kind: lesson
course: spaced-repetition
lesson: 02
title: Retrieval Practice
objectives: [O1, O2]
concepts: [retrieval-practice, desirable-difficulty]
requires: [01]              # lesson numbers this builds on; [] for none
est_minutes: 15
sources:
  - https://www.youtube.com/watch?v=VIDEO_ID
---
```

`lesson` is the two-digit string matching the filename. `concepts` must equal that lesson's
line in the index concept map (same ids, any order). `objectives` must be ids declared in the
index.

Body — these headings, in this order:

1. `# {title}`
2. `## Why this matters` — 2-4 sentences connecting to the learner's goal.
3. `## Core ideas` — one `###` sub-section per concept, heading written as
   ``### Retrieval practice (`retrieval-practice`)`` — the id in backticks is how tools map
   prose to concepts. Explain from first principles; define a term before using it.
4. `## Worked example` — one concrete, fully worked case. Not a hypothetical wave of the hand.
5. `## Common mistakes` — the misconceptions and misuses a learner is likely to hold.
6. `## Recap` — 3-5 bullets.
7. `## Check yourself` — 2-4 questions for self-study. **No answers here**; answers and rubrics
   live in `assessment.md` so a learner reading ahead does not spoil their own quiz.

## 6. `assessment.md` (tutor-facing)

The quiz bank. A tutor reads it; a learner should not read it before being quizzed (the
compiled `course.html` leaves it out).

```
---
kind: assessment
course: spaced-repetition
audience: tutor
---

# Assessment — Spaced Repetition, From First Principles

## retrieval-practice
- lesson: 02
- weight: threshold
- probe: Without looking anything up, explain why trying to recall an answer strengthens memory more than re-reading it, and give one study habit that follows.
- must_include:
  - recall itself is the strengthening event (effortful reconstruction), not exposure
  - re-reading produces familiarity that is mistaken for knowing
  - a concrete habit, e.g. closed-book self-testing before checking notes
- misconceptions:
  - "Testing only measures learning" -> the act of retrieval changes what is stored
- transfer: A colleague highlights every page of a manual the night before an audit. What would you change, and why?
```

One `## {concept-id}` section per concept in the concept map (and nothing else at `##` level).
Fields, as bullet lines exactly as shown:

| Field | Required | Meaning |
|---|---|---|
| `lesson` | yes | two-digit lesson number; must match the concept map |
| `weight` | yes | `core` or `threshold` (a threshold concept unlocks the rest — teach it slower, check it harder) |
| `probe` | yes | a free-recall question: the learner must **generate** an answer, never pick one |
| `must_include` | yes | 2-5 points a correct answer contains — the grading rubric |
| `misconceptions` | no | `wrong belief -> why it is wrong` lines, for diagnosing bad answers |
| `transfer` | no | a new situation that tests use, not recall |

**Alignment rule.** Every `must_include` point must be something the probe actually asks for.
The test: read the probe alone, answer it as a good learner would, then mark that answer
against the rubric. A point a good answer would never mention is a rubric defect — fix the
probe or drop the point. The reverse also holds: do not "fix" a point that the probe plainly
does request just because an automated checker flagged a word.

## 7. `99-practicum.md` (practicum spec)

A course that ends in lessons trains recall; the practicum is where it becomes usable. Every
course has one.

```
---
kind: practicum-spec
course: spaced-repetition
title: Practicum — Spaced Repetition, From First Principles
concepts: [retrieval-practice, spacing-effect]
---
```

Body — these four headings, in this order:

1. `## Concepts under test` — the load-bearing concept ids the task must force the learner to
   use (not all of them), each with one line on how the task exercises it.
2. `## Acceptance criteria` — how anyone can tell the result is correct, written for a grader
   who never saw the work being done. Runnable checks beat prose.
3. `## Shape of a good task` — what makes a target suitable for *this* course, so whoever runs
   the practicum can recognise a fit in a real codebase or situation.
4. `## Anti-tasks` — targets that look suitable but teach nothing here, and why.

**The spec never names the concrete target.** A target fixed at build time is stale by the
time someone sits down to do it; the practicum runner chooses real candidates against the
learner's situation at practicum time.

## 8. `progress.md` (reserved — owned by the tutor and practicum)

course-builder **never creates, edits, or deletes** this file, including on rebuild. The
shape below is the shared minimum so tutors and practicum runners agree; they may add
sections.

```
---
kind: progress
course: spaced-repetition
started: 2026-09-28
updated: 2026-09-30
lessons_completed: 1
practicum: not-started      # not-started | in-progress | done
---

# Progress — Spaced Repetition, From First Principles

## Concept status
- forgetting-curve: retained (last: 2026-09-30)
- decay-rate: retained (last: 2026-09-30)
- retrieval-practice: learning (last: 2026-09-30)

## Log
### 2026-09-30 — tutoring
- Reviewed lesson 01; both concepts recalled cleanly on the probe.
- retrieval-practice: missed the "familiarity is not knowing" point; re-explained with the worked example.
```

- Concept status values: `new` | `learning` | `retained` | `lapsed`. The status block is
  current state and is updated in place; a concept absent from it is `new`.
- `lessons_completed` = the number of lessons `01`..`NN` whose concepts (from the index
  concept map) are **all** `retained`. The `99` line never counts. Recompute it; never
  increment it by hand.
- `## Log` is append-only, newest entry last, absolute dates. Never rewrite past entries.
- If an external learning engine holds the authoritative schedule (see `engram_topic` in the
  index), the status block mirrors it; the engine wins on conflict.

Who writes what (so two consumers never fight over one field):

| Part | Owner | Notes |
|---|---|---|
| file creation, `started` | whichever consumer runs first | creates `practicum: not-started` if absent |
| `## Concept status`, `lessons_completed` | tutor | the practicum runner never edits concept status |
| `## Review schedule` (optional) | tutor | lines `- {concept-id}: box N, due YYYY-MM-DD` |
| `practicum:` | practicum runner | `not-started` -> `in-progress` -> `done` |
| `updated` | both | set on every write |
| `## Log` | both | append-only entries, headed `### YYYY-MM-DD — tutoring` or `— practicum` |

## 9. Changing a course after it exists

- **Extend, don't renumber.** New lessons are appended as the next numbers. Renumbering or
  renaming lessons or concept ids once a `progress.md` exists silently breaks the learner's
  record. If a restructure is truly needed, build a new course with a new slug.
- Bump `updated:` in the index and recompile `course.html` if one exists.
- Re-run `scripts/check_course.py`.

## 10. `course.html` (optional compiled version)

Generated by `scripts/compile_html.py <course-dir>`: one self-contained file, no external
requests, containing the index, every lesson in order, and the practicum spec as the closing
section. It deliberately excludes `assessment.md`. It is a derived file — regenerate it,
never hand-edit it; the Markdown files are the source of truth.
