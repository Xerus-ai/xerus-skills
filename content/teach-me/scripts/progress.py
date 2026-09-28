#!/usr/bin/env python3
"""teach-me progress helper (Python 3 stdlib only).

Reads a course folder (index.md concept map, assessment.md) and owns the
arithmetic of its progress.md, so the tutor never schedules reviews or counts
completed lessons "by feel". Formats: references/course-format.md and
references/progress-format.md. If Python is unavailable, the tutor applies the
same rules by hand.

Commands (COURSE is the course folder, the one holding index.md):

  status COURSE [--today YYYY-MM-DD]        per-lesson summary, next lesson, reviews due
  due    COURSE [--today YYYY-MM-DD]        concepts due for review, most overdue first
  item   COURSE CONCEPT                     print that concept's assessment.md entry
  grade  COURSE CONCEPT GRADE [--today D]   apply one grader verdict
                                            GRADE: recalled | partial | missed
  log    COURSE --file ENTRY.md [--today D] append a dated '### YYYY-MM-DD — tutoring'
                                            entry to ## Log
  draw                                      draw a random question type (1-7)

grade and log create progress.md on first use. Learner text (answers, notes,
log entries) travels in a file, never on the command line.
"""
import argparse
import datetime as dt
import os
import random
import re
import sys
import tempfile

GRADES = ("recalled", "partial", "missed")
STATUSES = ("new", "learning", "retained", "lapsed")
# Days until the next review after landing in box N. Box 0 = not yet recalled.
INTERVALS = {0: 1, 1: 2, 2: 5, 3: 12, 4: 30, 5: 75, 6: 180}
MAX_BOX = 6
QUESTION_TYPES = [
    "Find the break",
    "Fix it",
    "Predict",
    "Symptom to cause",
    "Pick and defend",
    "Tell them apart",
    "Push back",
]
# Concept ids: lowercase kebab-case (course format). Validated on load, so every
# id that can be graded can also be read back from progress.md.
ID = r"[a-z0-9][a-z0-9-]*"
ID_RE = re.compile(rf"^{ID}$")
STATUS_RE = re.compile(rf"^- ({ID}): (new|learning|retained|lapsed)(?: \(last: (\d{{4}}-\d{{2}}-\d{{2}})\))?\s*$")
SCHEDULE_RE = re.compile(rf"^- ({ID}): box (\d+), due (\d{{4}}-\d{{2}}-\d{{2}})\s*$")
MAP_RE = re.compile(r"^- (\d{2}): (.*)$")


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def today(arg):
    if not arg:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(arg)
    except ValueError:
        die(f"--today must be YYYY-MM-DD, got {arg!r}")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def write(path, text):
    # Temp file + replace: an interrupted write never leaves half a progress file.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".progress-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def split_frontmatter(text):
    """Return (frontmatter lines, body). Only the flat subset of the course format is used."""
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return [], text
    return m.group(1).split("\n"), text[m.end():]


def fm_value(lines, key):
    for line in lines:
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return None


def fm_set(lines, key, value):
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[i] = f"{key}: {value}"
            return
    lines.append(f"{key}: {value}")


def sections(body):
    """Split a body into [(heading or None, [lines])] on '## ' headings, keeping order."""
    out = [(None, [])]
    for line in body.split("\n"):
        if line.startswith("## "):
            out.append((line[3:].strip(), []))
        else:
            out[-1][1].append(line)
    return out


def join_sections(parts):
    chunks = []
    for heading, lines in parts:
        if heading is not None:
            chunks.append(f"## {heading}")
        chunks.extend(lines)
    return "\n".join(chunks).rstrip("\n") + "\n"


def section_lines(parts, heading):
    for h, lines in parts:
        if h == heading:
            return lines
    return None


# --- the course ------------------------------------------------------------

def load_course(course):
    index = os.path.join(course, "index.md")
    if not os.path.exists(index):
        die(f"{index} not found - is {course} a course folder?")
    fm, body = split_frontmatter(read(index))
    if fm_value(fm, "kind") != "course":
        die(f"{index} frontmatter lacks kind: course")
    concept_map = {}  # concept id -> lesson number ("01".."NN", or "99")
    lessons = []
    for line in section_lines(sections(body), "Concept map") or []:
        m = MAP_RE.match(line.strip())
        if not m:
            continue
        num = m.group(1)
        if num != "99":
            lessons.append(num)
        for cid in (c.strip() for c in m.group(2).split(",")):
            if not cid:
                continue
            if not ID_RE.match(cid):
                die(f"concept id {cid!r} in the concept map is not lowercase kebab-case")
            if cid in concept_map:
                die(f"concept id {cid!r} appears in lessons {concept_map[cid]} and {num}; "
                    "each concept belongs to exactly one lesson")
            concept_map[cid] = num
    if not lessons:
        die(f"{index} has no parseable '## Concept map' lines ('- 01: concept-a, concept-b')")
    return {
        "dir": course,
        "slug": fm_value(fm, "slug") or os.path.basename(os.path.abspath(course)),
        "title": fm_value(fm, "title") or "",
        "assessment": fm_value(fm, "assessment") or "assessment.md",
        "lessons": lessons,
        "concepts": concept_map,
    }


# --- progress.md -----------------------------------------------------------

def progress_path(course):
    return os.path.join(course["dir"], "progress.md")


def new_progress_text(course, day):
    return (
        "---\n"
        "kind: progress\n"
        f"course: {course['slug']}\n"
        f"started: {day}\n"
        f"updated: {day}\n"
        "lessons_completed: 0\n"
        "practicum: not-started\n"
        "---\n\n"
        f"# Progress — {course['title']}\n\n"
        "## Concept status\n\n"
        "## Review schedule\n\n"
        "## Log\n"
    )


def load_progress(course, create_on=None):
    path = progress_path(course)
    if not os.path.exists(path):
        if create_on is None:
            return None
        write(path, new_progress_text(course, create_on.isoformat()))
    fm, body = split_frontmatter(read(path))
    parts = sections(body)
    for heading in ("Concept status", "Review schedule", "Log"):
        if section_lines(parts, heading) is None:
            parts.append((heading, [""]))
    status, schedule = {}, {}
    for line in section_lines(parts, "Concept status"):
        m = STATUS_RE.match(line.strip())
        if m:
            status[m.group(1)] = {"status": m.group(2), "last": m.group(3)}
    for line in section_lines(parts, "Review schedule"):
        m = SCHEDULE_RE.match(line.strip())
        if m:
            schedule[m.group(1)] = {"box": int(m.group(2)), "due": m.group(3)}
    return {"path": path, "fm": fm, "parts": parts, "status": status, "schedule": schedule}


def completed_lessons(course, prog):
    status = prog["status"] if prog else {}
    done = []
    for num in course["lessons"]:
        ids = [c for c, n in course["concepts"].items() if n == num]
        if ids and all(status.get(c, {}).get("status") == "retained" for c in ids):
            done.append(num)
    return done


def save_progress(course, prog, day):
    order = list(course["concepts"])  # concept-map order keeps the file readable
    known = [c for c in order if c in prog["status"]] + [c for c in prog["status"] if c not in course["concepts"]]
    status_lines = [""] + [
        f"- {c}: {prog['status'][c]['status']}" + (f" (last: {prog['status'][c]['last']})" if prog["status"][c]["last"] else "")
        for c in known
    ] + [""]
    sched = [c for c in order if c in prog["schedule"]] + [c for c in prog["schedule"] if c not in course["concepts"]]
    schedule_lines = [""] + [f"- {c}: box {prog['schedule'][c]['box']}, due {prog['schedule'][c]['due']}" for c in sched] + [""]
    parts = []
    for heading, lines in prog["parts"]:
        if heading == "Concept status":
            lines = status_lines
        elif heading == "Review schedule":
            lines = schedule_lines
        parts.append((heading, lines))
    fm = prog["fm"]
    fm_set(fm, "updated", day.isoformat())
    fm_set(fm, "lessons_completed", str(len(completed_lessons(course, prog))))
    write(prog["path"], "---\n" + "\n".join(fm) + "\n---\n" + join_sections(parts))


def due_rows(prog, day):
    rows = []
    for cid, s in (prog["schedule"] if prog else {}).items():
        due = dt.date.fromisoformat(s["due"])
        if due <= day:
            rows.append(((day - due).days, cid))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return rows


# --- commands --------------------------------------------------------------

def cmd_status(a):
    course = load_course(a.course)
    prog = load_progress(course)
    day = today(a.today)
    status = prog["status"] if prog else {}
    done = completed_lessons(course, prog)
    print(f"{course['title']} ({course['slug']})" + ("" if prog else " - not started, no progress.md yet"))
    next_lesson = None
    for num in course["lessons"]:
        ids = [c for c, n in course["concepts"].items() if n == num]
        counts = {s: 0 for s in STATUSES}
        for c in ids:
            counts[status.get(c, {}).get("status", "new")] += 1
        if next_lesson is None and counts["new"]:
            next_lesson = num
        mark = "done" if num in done else "open"
        detail = ", ".join(f"{counts[s]} {s}" for s in STATUSES if counts[s])
        print(f"  lesson {num}: {mark} - {detail}")
    print(f"lessons completed: {len(done)}/{len(course['lessons'])}")
    print(f"next lesson to teach: {next_lesson or 'none (all concepts started)'}")
    print(f"reviews due: {len(due_rows(prog, day))}")


def cmd_due(a):
    course = load_course(a.course)
    rows = due_rows(load_progress(course), today(a.today))
    if not rows:
        print("nothing due")
    for overdue, cid in rows:
        print(f"{cid}\tlesson {course['concepts'].get(cid, '?')}\toverdue {overdue}d")


def assessment_entry(course, concept):
    """The concept's assessment.md entry. No entry = no rubric = cannot be graded."""
    path = os.path.join(course["dir"], course["assessment"])
    if not os.path.exists(path):
        die(f"{path} not found - without a rubric nothing can be graded")
    _, body = split_frontmatter(read(path))
    lines = section_lines(sections(body), concept)
    if lines is None:
        die(f"no '## {concept}' entry in {path} - this concept cannot be graded")
    return f"## {concept}\n" + "\n".join(lines).strip()


def cmd_item(a):
    print(assessment_entry(load_course(a.course), a.concept))


def cmd_grade(a):
    if a.grade not in GRADES:
        die(f"grade must be one of {GRADES}")
    course = load_course(a.course)
    if a.concept not in course["concepts"]:
        die(f"{a.concept!r} is not in the index concept map")
    assessment_entry(course, a.concept)  # refuse to grade without a rubric
    day = today(a.today)
    prog = load_progress(course, create_on=day)
    cur = prog["status"].get(a.concept, {"status": "new", "last": None})
    sched = prog["schedule"].get(a.concept, {"box": 0, "due": None})
    # One scheduled grade per concept per day. A second attempt the same day is
    # practice: the tutor logs it, but it does not move the schedule. This also
    # makes a retried or duplicated grade call harmless.
    if cur["last"] == day.isoformat():
        print(f"{a.concept}: {a.grade} is PRACTICE (already graded today) - schedule unchanged, "
              f"{cur['status']}, due {sched['due']}")
        return
    box = sched["box"]
    ever_recalled = cur["status"] in ("retained", "lapsed")
    if a.grade == "recalled":
        box, new_status = min(box + 1, MAX_BOX), "retained"
        days = INTERVALS[box]
    elif a.grade == "partial":
        new_status = cur["status"] if cur["status"] != "new" else "learning"
        days = max(1, INTERVALS[box] // 2)
    else:
        box, new_status = 0, ("lapsed" if ever_recalled else "learning")
        days = INTERVALS[0]
    due = (day + dt.timedelta(days=days)).isoformat()
    prog["status"][a.concept] = {"status": new_status, "last": day.isoformat()}
    prog["schedule"][a.concept] = {"box": box, "due": due}
    save_progress(course, prog, day)
    print(f"{a.concept}: {a.grade} -> {new_status}, box {box}, next review {due}; "
          f"lessons completed {len(completed_lessons(course, prog))}/{len(course['lessons'])}")


def cmd_log(a):
    course = load_course(a.course)
    day = today(a.today)
    prog = load_progress(course, create_on=day)
    entry = read(a.file).strip()
    if not entry:
        die(f"{a.file} is empty")
    parts = prog["parts"]
    for i, (heading, lines) in enumerate(parts):
        if heading == "Log":
            while lines and not lines[-1].strip():
                lines.pop()
            lines += ["", f"### {day.isoformat()} — tutoring", entry, ""]
            parts[i] = (heading, lines)
    save_progress(course, prog, day)
    print(f"logged tutoring entry for {day.isoformat()}")


def cmd_draw(a):
    n = random.SystemRandom().randint(1, len(QUESTION_TYPES))
    print(f"{n} {QUESTION_TYPES[n - 1]}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # some consoles default to a legacy codepage
    p = argparse.ArgumentParser(description="teach-me progress helper")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("status", cmd_status), ("due", cmd_due)):
        s = sub.add_parser(name); s.add_argument("course"); s.add_argument("--today"); s.set_defaults(fn=fn)
    s = sub.add_parser("item"); s.add_argument("course"); s.add_argument("concept"); s.set_defaults(fn=cmd_item)
    s = sub.add_parser("grade"); s.add_argument("course"); s.add_argument("concept"); s.add_argument("grade")
    s.add_argument("--today"); s.set_defaults(fn=cmd_grade)
    s = sub.add_parser("log"); s.add_argument("course"); s.add_argument("--file", required=True)
    s.add_argument("--today"); s.set_defaults(fn=cmd_log)
    s = sub.add_parser("draw"); s.set_defaults(fn=cmd_draw)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
