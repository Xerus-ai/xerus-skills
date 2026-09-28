# What teach-me reads from a course folder

teach-me tutors from a course folder in "course format 1" (the format a course-builder skill
writes). This page restates only the parts teach-me depends on, so the skill works when it is
installed on its own. A hand-written course that follows this page works too.

## Finding courses

Stop at the first rule that finds anything:

1. a path the learner gave;
2. `courses/*/index.md` at the repository root;
3. any `index.md` in the repository whose frontmatter has `kind: course` (skip `.git/`,
   `node_modules/`, virtual environments and build output).

A course is identified by the `slug` in its index frontmatter.

## Layout

```
{slug}/
  index.md            course map (required)
  01-{lesson}.md      lessons 01..NN, contiguous (required)
  assessment.md       probes + rubrics, one entry per concept (required for grading)
  99-practicum.md     practicum spec (teach-me only points the learner to it once all lessons are done)
  course.html         optional reading copy; excludes assessment.md
  sources/            optional captured source text (teach-me does not use it)
  practicum/          optional, a practicum runner's working folder (teach-me leaves it alone)
  progress.md         the learner's record - written by teach-me (and a practicum runner)
```

Concept ids must be lowercase kebab-case (`a-z`, `0-9`, `-`, starting with a letter or digit)
and each appears in exactly one concept-map line. `scripts/progress.py` refuses a course that
breaks either rule rather than lose grades for a malformed id.

Frontmatter everywhere uses a flat subset: `key: value`, `key: [a, b]`, or a key followed by
`  - item` lines. No nesting.

## index.md

Frontmatter keys teach-me uses: `kind: course`, `slug`, `title`, `lessons` (count),
`assessment` (usually `assessment.md`), and optionally `engram_topic`.

Body sections teach-me uses:

- `## Learning objectives` - `- O1: ...` lines. Useful for telling the learner where they are
  heading; not graded directly.
- `## Lessons` - numbered list linking each lesson file with a one-line goal.
- `## Concept map` - **the line grammar teach-me parses**:

  ```
  - 01: forgetting-curve, decay-rate
  - 02: retrieval-practice, desirable-difficulty
  - 99: capstone-only-concept
  ```

  One line per lesson, `- NN: ` then comma-separated concept ids (lowercase kebab-case). Every
  concept appears in exactly one lesson. A `99` line lists practicum-only concepts and is never
  counted as a lesson.
- `## Concept dependencies` (optional) - `- spacing-effect <- forgetting-curve, retrieval-practice`.
  When a learner stalls on a concept, re-teach what it builds on first.

## Lesson files `NN-{lesson}.md`

Frontmatter: `lesson: NN`, `title`, `concepts: [...]` (same ids as the concept-map line),
`requires: [...]` (earlier lesson numbers).

Body, in order: `## Why this matters`, `## Core ideas` (one `###` per concept, headed like
``### Retrieval practice (`retrieval-practice`)`` - the id in backticks maps prose to concept),
`## Worked example`, `## Common mistakes`, `## Recap`, `## Check yourself` (self-study
questions, no answers).

## assessment.md (tutor-facing, never shown to the learner)

One `## {concept-id}` section per concept:

```
## retrieval-practice
- lesson: 02
- weight: threshold
- probe: Without looking anything up, explain why trying to recall an answer strengthens memory more than re-reading it, and give one study habit that follows.
- must_include:
  - recall itself is the strengthening event, not exposure
  - re-reading produces familiarity that is mistaken for knowing
  - a concrete habit, e.g. closed-book self-testing before checking notes
- misconceptions:
  - "Testing only measures learning" -> the act of retrieval changes what is stored
- transfer: A colleague highlights every page of a manual the night before an audit. What would you change, and why?
```

- `probe` - a free-recall question; the reference question for the concept.
- `must_include` - 2-5 points a correct answer shows. **This is the rubric.**
- `weight` - `threshold` concepts unlock the rest: teach them slower, check them harder.
- `misconceptions` (optional) - `wrong belief -> why it is wrong`, for diagnosing answers.
- `transfer` (optional) - a new situation that tests use rather than recall.

## progress.md

Reserved for the learner's record; a course builder never writes it. Its shape is in
`progress-format.md`.

## Rules teach-me keeps because of this format

- Concept ids are stable forever once `progress.md` exists. teach-me never renames them.
- Lessons and `assessment.md` are course content. teach-me reads them; it does not rewrite
  lessons, and it edits an `assessment.md` entry only with the learner's explicit OK (see
  `grading.md`, "Defective rubrics").
