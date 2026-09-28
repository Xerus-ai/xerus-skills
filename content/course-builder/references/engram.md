# Optional: registering a course with the engram learning plugin

[Engram](https://github.com/nagisanzenin/engram) is a Claude Code plugin for spaced-retrieval
learning: FSRS scheduling, a curriculum architect / tutor / blind assessor split, all state local.
If it is installed, a course can be registered as an engram *topic* so a tutor can schedule
reviews of its concepts. **Everything in course-builder works without it**; skip this file if the
plugin is not present.

## Detect

Engram is available when its agents are (an agent type named like
`engram:engram-curriculum-architect`) or its `/learn` command is listed. If not:

- set `engram_topic: none` in the index (or `pending-install` if the user says they intend to
  install it, so a later run knows to finish registration), and stop here;
- installing a plugin is the user's call, not the skill's. Mention it once, do not install it.

## Register without starting a study session

`/learn` begins a live tutoring session; a build step must not fire it. Registration is two moves:

1. Spawn the curriculum-architect agent with the course's `index.md`, lesson files and
   `assessment.md` as the curriculum source. Tell it the topic slug explicitly (use the course
   slug) and ask it to **reuse the course's concept ids as node ids** wherever a node matches a
   concept.
2. Feed the JSON it returns to the plugin's CLI: `engram.py add-topic --file <that json>`
   (locate `engram.py` inside the plugin's install directory; use whichever Python launcher the
   system has).

Then set `engram_topic: {topic id}` in the index frontmatter and tell the user they can start
with `/learn {topic}`.

## Keep the concept map true

The tutor computes `lessons_completed` from the index concept map, so the map must name the
nodes engram actually tracks:

- If engram's node ids differ from the course's concept ids, rename the course side to match
  (index concept map, lesson `concepts:` and `###` headings, `assessment.md` sections) **before
  any `progress.md` exists**. After that, ids are frozen (course-format section 9).
- Every node sits in exactly one lesson: the one that teaches it most directly, judged by reading
  the lessons, not the titles. Nodes the architect adds that no lesson teaches (such as a
  capstone node) go on a `- 99: ...` line, which never counts as a lesson.
- Re-run `python .claude/skills/course-builder/scripts/check_course.py {course-dir}` after any
  rename.

## Triage add-topic warnings; do not reflex-fix them

Engram's probe/rubric check is a heuristic and produces false positives (it has flagged criteria
that the probe plainly asked for, tripping on a single word). For each warning: read the probe
alone, answer it, mark that answer against the rubric. Only a criterion the probe genuinely never
requests is a defect. Repair real defects through the plugin's node-edit command (pass edits as a
file, never inline learner text) and re-run its doctor until the probe-gap count is 0, so the
warning does not nag every future run into "fixing" sound nodes.

## Platform note

Engram prints non-ASCII. On consoles whose default encoding is not UTF-8 (common on Windows),
set `PYTHONIOENCODING=utf-8` for every engram call, or a healthy install will crash with a
`UnicodeEncodeError`.
