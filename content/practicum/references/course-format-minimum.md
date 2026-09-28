# What practicum needs from a course

Practicum reads courses in a plain Markdown folder format ("format 1"). This
file restates only the parts practicum depends on, so the skill works on its
own. If a course-building skill that writes this format is installed, its
documentation is the fuller contract. Where the two differ, go with the
course's actual files and say what you saw.

A course that does not follow this format can still be used. See "No
conforming course" at the end.

## Finding courses

Stop at the first rule that finds something:

1. A path the user gave explicitly.
2. `courses/*/index.md` at the repository root.
3. Any `index.md` in the repo whose frontmatter has `kind: course`. Skip
   `.git/`, `node_modules/`, virtualenvs and build output.

A course is identified by the `slug` in its index frontmatter.

## Frontmatter

Every course file opens with a `---` block. Only three shapes appear, so a
reader does not need a YAML library:

```
key: scalar value
key: [item-one, item-two]
key:
  - item one
  - item two
```

Quotes around scalars are optional. Dates are `YYYY-MM-DD`.

## The files practicum reads

```
{course-dir}/
  index.md          kind: course; slug, title, practicum: 99-practicum.md
  NN-{lesson}.md    lessons 01..NN (read only when the spec leans on one)
  assessment.md     tutor-facing probes, one "## {concept-id}" section each
  99-practicum.md   the practicum spec: the artifact rubric
  progress.md       learner progress (practicum reads it and appends to it)
```

### `index.md`

Practicum uses `slug`, `title` and `practicum` from the frontmatter, plus the
`## Concept map` section. That section has one line per lesson:

```
- 01: concept-a, concept-b
- 02: concept-c
- 99: concept-only-the-practicum-uses
```

The optional `- 99:` line lists concepts that only the practicum exercises.
The recall gate ignores that line: no lesson teaches those concepts, so the
tutor never gives them a status. It gates only on spec concepts that appear on
a lesson line (`01`..`NN`).

### `99-practicum.md` (the spec)

The frontmatter has `kind: practicum-spec`, `course`, `title`, and
`concepts: [...]` (the concept ids under test). The body has four headings, in
this order:

1. `## Concepts under test`: the load-bearing concepts, each with how the task
   must exercise it.
2. `## Acceptance criteria`: how a grader who never saw the build can tell the
   result is correct.
3. `## Shape of a good task`: what makes a real target fit this course.
4. `## Anti-tasks`: targets that look like a fit but teach nothing here.

**The spec never names a concrete target.** Practicum picks targets from the
live codebase when the session starts. A spec that does name one is treated as
one candidate among three, not as the answer.

### `assessment.md`

One `## {concept-id}` section per concept, with bullet fields including
`probe:` (a free-recall question) and `must_include:` (the points a correct
answer contains). Practicum uses this only in the recall gate, and only when
no tutor skill is available.

### `progress.md`

Shared by the tutor and practicum. If it is missing, practicum creates it with
this minimum shape:

```
---
kind: progress
course: {slug}
started: YYYY-MM-DD
updated: YYYY-MM-DD
lessons_completed: 0
practicum: not-started
---

# Progress — {title}

## Concept status

## Log
```

Rules practicum follows:

- **Concept status** lines look like `- concept-id: retained (last: YYYY-MM-DD)`.
  The values are `new | learning | retained | lapsed`, and a concept that is
  absent counts as `new`. Practicum **reads** this for the recall gate and
  **never writes it**. Grading recall belongs to the tutor.
- **`practicum:`** is `not-started | in-progress | done`. Practicum owns this
  field. It becomes `in-progress` when an attempt is contracted and `done`
  when an attempt is graded. An abandoned attempt sets it back to the previous
  value.
- **`updated:`** gets bumped whenever practicum writes.
- **`## Log`** is append-only, with the newest entry last and absolute dates.
  Practicum appends a new entry, headed exactly `### YYYY-MM-DD — practicum`,
  when an attempt starts and again when it is graded or abandoned. The first
  bullet names the attempt (`- attempt NN: ...`). It never edits or adds to an
  old entry, even one from earlier the same day.
- **Creating the file**: whichever consumer runs first creates `progress.md`,
  with `practicum: not-started`.
- **`lessons_completed`** is computed by the tutor. Practicum leaves it alone.

## What practicum adds to a course folder

```
{course-dir}/practicum/
  attempt-01.md         the practicum record (see practicum-record.md)
  attempt-01/           evidence: check output, patch, grading bundle, grade
  attempt-02.md
  ...
```

Nothing else in the course folder is created or edited by practicum.

## No conforming course

If the user wants a practicum on a course that has no `99-practicum.md` (or no
course folder at all, just a topic they studied), do not invent a spec on your
own. Offer to draft one **with** the human using the four headings above.
Write it to `{course-dir}/99-practicum.md`, or to `practicum/{topic-slug}/spec.md`
at the repo root when there is no course folder. The human must confirm the
acceptance criteria before any target is proposed: the criteria are the
artifact rubric, and a rubric the builder wrote alone and the grader then
applies is the builder grading their own work one step removed. Record in the
attempt's frontmatter that the spec was drafted at practicum time
(`spec: drafted-at-practicum`).
