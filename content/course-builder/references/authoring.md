# Authoring rules: plan, lessons, assessment, practicum

The format says where things go (`course-format.md`). This file says what makes them good.

## Planning

- **Objectives first.** Write 3-6 course objectives before any lesson. Each is observable:
  "explain", "diagnose", "choose between", "build", "predict". If an objective starts with
  "understand" or "know", rewrite it until you could tell whether someone met it.
- **Concepts, not chapters.** List the ideas a learner must hold, as kebab-case ids. A concept is
  one idea that can be probed with one question. "Caching" is a chapter; `cache-invalidation`
  and `write-through-vs-write-back` are concepts. Aim for 2-4 concepts per lesson.
- **Order prerequisite-first.** A lesson may only use concepts taught in itself or in the lessons
  it `requires`. If lesson 3 needs something from lesson 5, reorder.
- **Mark the threshold concepts.** The one or two ideas that, once they click, make the rest easy
  (and without which the rest is memorisation). They get `weight: threshold` in the assessment
  and more room in their lesson.
- **4-8 lessons is the normal range.** Fewer than 4 usually means the material is one lesson; more
  than 8 usually means two courses. A lesson should take 10-25 minutes to read carefully.
- **Coverage check before writing.** Every objective is served by at least one lesson; every
  lesson serves at least one objective; every concept maps to exactly one lesson.

## Lessons

- **Explain from first principles.** Define each term before use. Build from something the
  learner already has (a prerequisite concept or everyday experience), not from jargon.
- **One worked example that is actually worked.** Concrete numbers, real code, a real situation
  from the sources, carried through to the end. The example is where the learner sees the idea
  do something.
- **Common mistakes come from the material.** The anti-patterns and warnings the sources gave, and
  the misconceptions a newcomer predictably brings. These feed the assessment's `misconceptions`.
- **Use the source's substance, not its sequence.** A video's order is the speaker's; the course
  order is prerequisite order. Merge overlapping material from different sources into one
  explanation rather than repeating it per source.
- **Cite where it came from.** Lesson `sources:` lists what the lesson drew on. When a specific
  claim comes from a video, a timestamp in the prose (`(source video, 12:40)`) lets the learner
  and the tutor go back to it.
- **No filler.** If the material runs out, the lesson is short. A thin lesson with an honest
  provenance note beats a padded one.
- **Check yourself** questions are for self-study and have no answers in the lesson. Make them
  generative ("explain", "sketch", "design"), not yes/no.

## Assessment

- **Probes ask for generation.** Free recall or explanation, never multiple choice, never
  "true or false". The learner produces the answer.
- **Rubric points are what a correct answer must contain**, 2-5 of them, each checkable on its
  own. Not "good understanding of X".
- **Alignment test, every entry.** Read the probe alone, write the answer a strong learner would
  give, then mark it against `must_include`. A point that answer never mentions means the probe
  does not ask for it: rewrite the probe or drop the point. Conversely, if a point is plainly
  requested, leave it alone even when a keyword-based checker complains.
- **Transfer questions use a new situation**, not the lesson's own example. They are how a tutor
  tells recall from understanding.
- **Misconceptions are diagnostic**: `wrong belief -> why it is wrong`, so a tutor who hears the
  wrong belief knows what to re-teach.

## Practicum spec

Every course gets one. It names four things and deliberately **not** a target:

1. **Concepts under test** — the load-bearing concepts only, each with how the task forces it.
2. **Acceptance criteria** — observable, written for a grader who never saw the work. Prefer
   runnable checks ("the test suite has a failing test that the fix makes pass") to prose.
3. **Shape of a good task** — what makes a real target suitable for this course.
4. **Anti-tasks** — targets that look suitable but teach nothing here. Naming these is what stops
   a vague capstone ("build something with X").

A concrete target chosen now is stale by the time the learner sits down. The practicum runner
(for example a `practicum` skill, or the learner with a mentor) picks real candidates against the
learner's live situation at that time.

## Final read-through

Before running the checker, read the index as a stranger: does the summary say what the learner
will be able to do? Do the lesson one-liners tell a story in order? Is the provenance section
honest about what was thin?
