#!/usr/bin/env python3
"""Validate a course folder against references/course-format.md (format 1).

Usage:
    python check_course.py <course-dir>

Prints every problem found and exits 1 if there are any, else prints a one-line
summary and exits 0. Python 3 stdlib only.
"""
import os
import re
import sys

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
LESSON_FILE_RE = re.compile(r"^(\d\d)-([a-z0-9][a-z0-9-]*)\.md$")
CONCEPT_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OBJ_RE = re.compile(r"^-\s+(O\d+)\s*:\s*\S")
MAP_RE = re.compile(r"^-\s+(\d\d)\s*:\s*(.+)$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

INDEX_HEADINGS = ["About this course", "Learning objectives", "Prerequisites", "Lessons",
                  "Concept map", "Practicum", "Provenance"]
LESSON_HEADINGS = ["Why this matters", "Core ideas", "Worked example", "Common mistakes",
                   "Recap", "Check yourself"]
PRACTICUM_HEADINGS = ["Concepts under test", "Acceptance criteria", "Shape of a good task",
                      "Anti-tasks"]
LEVELS = {"intro", "intermediate", "advanced"}
WEIGHTS = {"core", "threshold"}


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(text):
    """Parse the frontmatter subset: scalars, [inline, lists], and '  - block' lists.

    Returns (meta, body, error). error is None on success.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text, "missing frontmatter (file must start with ---)"
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text, "frontmatter is not closed with ---"
    meta, current = {}, None
    for n, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item:
            if current is None or not isinstance(meta.get(current), list):
                return {}, text, "frontmatter line %d: list item without a list key" % n
            meta[current].append(unquote(item.group(1)))
            continue
        pair = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if not pair:
            return {}, text, "frontmatter line %d: not 'key: value' -> %r" % (n, line)
        key, raw = pair.group(1), pair.group(2).strip()
        if raw == "":
            meta[key], current = [], key
        elif raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            meta[key] = [unquote(x) for x in inner.split(",")] if inner else []
            current = None
        else:
            meta[key], current = unquote(raw), None
    body = "\n".join(lines[end + 1:])
    return meta, body, None


def strip_code(body):
    """Body lines with fenced code blocks blanked out, so headings inside code are ignored."""
    out, fenced = [], False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return out


def headings(lines, level):
    prefix = "#" * level + " "
    return [l[len(prefix):].strip() for l in lines if l.startswith(prefix)]


def section(lines, title, level=2):
    """Lines under a heading of the given level, up to the next heading of that level or higher."""
    prefix = "#" * level + " "
    out, inside = [], False
    for line in lines:
        m = re.match(r"^(#{1,6}) ", line)
        if inside and m and len(m.group(1)) <= level:
            break
        if line.startswith(prefix) and line[len(prefix):].strip() == title:
            inside = True
            continue
        if inside:
            out.append(line)
    return out


def check_order(found, required, where, errors):
    pos = -1
    for h in required:
        if h not in found:
            errors.append("%s: missing heading '## %s'" % (where, h))
            continue
        i = found.index(h)
        if i < pos:
            errors.append("%s: heading '## %s' is out of order" % (where, h))
        pos = max(pos, i)


def as_list(meta, key):
    value = meta.get(key)
    if isinstance(value, list):
        return value
    return None


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check_links(name, body, files, errors):
    for target in LINK_RE.findall(body):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue  # external URL or in-page anchor
        target = target.split("#")[0]
        if "/" in target or "\\" in target:
            errors.append("%s: link '%s' leaves the course folder (sibling links only)" % (name, target))
        elif target not in files:
            errors.append("%s: link to missing file '%s'" % (name, target))


def check_course(course_dir):
    errors = []
    if not os.path.isdir(course_dir):
        return ["not a directory: %s" % course_dir], None
    files = set(os.listdir(course_dir))

    # ---- index.md --------------------------------------------------------
    if "index.md" not in files:
        return ["index.md is missing"], None
    meta, body, err = parse_frontmatter(read(os.path.join(course_dir, "index.md")))
    if err:
        return ["index.md: " + err], None
    lines = strip_code(body)
    for key in ("kind", "format", "slug", "title", "summary", "level", "created", "updated",
                "lessons", "assessment", "practicum"):
        if not meta.get(key):
            errors.append("index.md: frontmatter key '%s' is missing or empty" % key)
    if meta.get("kind") and meta["kind"] != "course":
        errors.append("index.md: kind must be 'course'")
    if meta.get("format") and meta["format"] != "1":
        errors.append("index.md: format must be 1")
    slug = meta.get("slug", "")
    if slug and not SLUG_RE.match(slug):
        errors.append("index.md: slug '%s' must match [a-z][a-z0-9-], max 48 chars" % slug)
    if meta.get("level") and meta["level"] not in LEVELS:
        errors.append("index.md: level must be one of %s" % sorted(LEVELS))
    for key in ("created", "updated"):
        if meta.get(key) and not DATE_RE.match(meta[key]):
            errors.append("index.md: %s must be YYYY-MM-DD" % key)
    if meta.get("assessment") and meta["assessment"] != "assessment.md":
        errors.append("index.md: assessment must be 'assessment.md'")
    if meta.get("practicum") and meta["practicum"] != "99-practicum.md":
        errors.append("index.md: practicum must be '99-practicum.md'")
    sources = as_list(meta, "sources")
    if not sources:
        errors.append("index.md: sources must be a non-empty list of what was actually read")
    if "engram_topic" in meta and not isinstance(meta["engram_topic"], str):
        errors.append("index.md: engram_topic must be a scalar")
    if lines and not any(l.startswith("# ") for l in lines):
        errors.append("index.md: missing '# {title}' heading")
    check_order(headings(lines, 2), INDEX_HEADINGS, "index.md", errors)

    objectives = []
    for line in section(lines, "Learning objectives"):
        m = OBJ_RE.match(line.strip())
        if m:
            objectives.append(m.group(1))
        elif line.strip():
            errors.append("index.md: objective line not '- O<n>: ...' -> %r" % line.strip())
    if not objectives:
        errors.append("index.md: no learning objectives ('- O1: ...')")
    if len(set(objectives)) != len(objectives):
        errors.append("index.md: duplicate objective ids")

    concept_map, concept_owner = {}, {}
    for line in section(lines, "Concept map"):
        if not line.strip():
            continue
        m = MAP_RE.match(line.strip())
        if not m:
            errors.append("index.md: concept map line not '- NN: id, id' -> %r" % line.strip())
            continue
        num, ids = m.group(1), [x.strip() for x in m.group(2).split(",") if x.strip()]
        if num in concept_map:
            errors.append("index.md: concept map has lesson %s twice" % num)
        concept_map[num] = ids
        for cid in ids:
            if not CONCEPT_RE.match(cid):
                errors.append("index.md: concept id '%s' is not kebab-case" % cid)
            if cid in concept_owner:
                errors.append("index.md: concept '%s' is mapped to lessons %s and %s (exactly one allowed)"
                              % (cid, concept_owner[cid], num))
            concept_owner[cid] = num
    check_links("index.md", body, files, errors)

    # ---- lesson files ----------------------------------------------------
    lesson_files = {}
    for f in sorted(files):
        m = LESSON_FILE_RE.match(f)
        if m and m.group(1) not in ("00", "99"):
            if m.group(1) in lesson_files:
                errors.append("two lesson files numbered %s" % m.group(1))
            lesson_files[m.group(1)] = f
    nums = sorted(lesson_files)
    expected = ["%02d" % i for i in range(1, len(nums) + 1)]
    if nums != expected:
        errors.append("lesson numbers must run 01..NN with no gaps; found %s" % nums)
    if not 2 <= len(nums) <= 12:
        errors.append("a course has 2-12 lessons; found %d" % len(nums))
    if meta.get("lessons") and meta["lessons"] != str(len(nums)):
        errors.append("index.md: lessons: %s but %d lesson files exist" % (meta["lessons"], len(nums)))
    lesson_list = section(lines, "Lessons")
    for num in nums:
        if not any(("(%s)" % lesson_files[num]) in l for l in lesson_list):
            errors.append("index.md: '## Lessons' does not link %s" % lesson_files[num])
        if num not in concept_map:
            errors.append("index.md: concept map has no line for lesson %s" % num)
    for num in concept_map:
        if num != "99" and num not in lesson_files:
            errors.append("index.md: concept map line %s has no lesson file" % num)

    for num in nums:
        name = lesson_files[num]
        lmeta, lbody, err = parse_frontmatter(read(os.path.join(course_dir, name)))
        if err:
            errors.append("%s: %s" % (name, err))
            continue
        llines = strip_code(lbody)
        for key in ("kind", "course", "lesson", "title", "est_minutes"):
            if not lmeta.get(key):
                errors.append("%s: frontmatter key '%s' is missing or empty" % (name, key))
        if lmeta.get("kind") and lmeta["kind"] != "lesson":
            errors.append("%s: kind must be 'lesson'" % name)
        if slug and lmeta.get("course") and lmeta["course"] != slug:
            errors.append("%s: course '%s' does not match index slug '%s'" % (name, lmeta["course"], slug))
        if lmeta.get("lesson") and lmeta["lesson"] != num:
            errors.append("%s: lesson: %s does not match filename number %s" % (name, lmeta["lesson"], num))
        for key in ("objectives", "concepts", "requires", "sources"):
            if as_list(lmeta, key) is None:
                errors.append("%s: '%s' must be a list" % (name, key))
        for oid in as_list(lmeta, "objectives") or []:
            if oid not in objectives:
                errors.append("%s: objective '%s' is not declared in the index" % (name, oid))
        if not as_list(lmeta, "objectives"):
            errors.append("%s: objectives must not be empty" % name)
        if not as_list(lmeta, "sources"):
            errors.append("%s: sources must not be empty" % name)
        for req in as_list(lmeta, "requires") or []:
            if req not in lesson_files or req >= num:
                errors.append("%s: requires '%s' is not an earlier lesson" % (name, req))
        concepts = as_list(lmeta, "concepts") or []
        if not concepts:
            errors.append("%s: concepts must not be empty" % name)
        if sorted(concepts) != sorted(concept_map.get(num, [])):
            errors.append("%s: concepts %s differ from the index concept map line %s: %s"
                          % (name, concepts, num, concept_map.get(num, [])))
        if not any(l.startswith("# ") for l in llines):
            errors.append("%s: missing '# {title}' heading" % name)
        check_order(headings(llines, 2), LESSON_HEADINGS, name, errors)
        core = headings(section(llines, "Core ideas"), 3)
        for cid in concepts:
            if not any(("`%s`" % cid) in h for h in core):
                errors.append("%s: no '### ... (`%s`)' heading under '## Core ideas'" % (name, cid))
        check = [l for l in section(llines, "Check yourself") if l.strip()]
        if not check:
            errors.append("%s: '## Check yourself' has no questions" % name)
        check_links(name, lbody, files, errors)

    # ---- assessment.md ---------------------------------------------------
    all_concepts = set(concept_owner)
    if "assessment.md" not in files:
        errors.append("assessment.md is missing")
    else:
        ameta, abody, err = parse_frontmatter(read(os.path.join(course_dir, "assessment.md")))
        if err:
            errors.append("assessment.md: " + err)
        else:
            alines = strip_code(abody)
            if ameta.get("kind") != "assessment":
                errors.append("assessment.md: kind must be 'assessment'")
            if slug and ameta.get("course") != slug:
                errors.append("assessment.md: course must be '%s'" % slug)
            if ameta.get("audience") != "tutor":
                errors.append("assessment.md: audience must be 'tutor'")
            entries = headings(alines, 2)
            for cid in sorted(all_concepts - set(entries)):
                errors.append("assessment.md: no '## %s' entry" % cid)
            for cid in entries:
                if cid not in all_concepts:
                    errors.append("assessment.md: '## %s' is not a concept in the concept map" % cid)
                    continue
                fields, current = {}, None
                for line in section(alines, cid):
                    top = re.match(r"^-\s+([a-z_]+)\s*:\s*(.*)$", line)
                    sub = re.match(r"^\s+-\s+(.+)$", line)
                    if top:
                        current = top.group(1)
                        fields[current] = top.group(2).strip() or []
                    elif sub and current and isinstance(fields.get(current), list):
                        fields[current].append(sub.group(1).strip())
                where = "assessment.md [%s]" % cid
                if fields.get("lesson") != concept_owner[cid]:
                    errors.append("%s: lesson must be %s (from the concept map)" % (where, concept_owner[cid]))
                if fields.get("weight") not in WEIGHTS:
                    errors.append("%s: weight must be core or threshold" % where)
                if not isinstance(fields.get("probe"), str) or not fields.get("probe"):
                    errors.append("%s: probe is missing" % where)
                must = fields.get("must_include")
                if not isinstance(must, list) or not 2 <= len(must) <= 5:
                    errors.append("%s: must_include needs 2-5 sub-bullets" % where)

    # ---- 99-practicum.md -------------------------------------------------
    if "99-practicum.md" not in files:
        errors.append("99-practicum.md is missing")
    else:
        pmeta, pbody, err = parse_frontmatter(read(os.path.join(course_dir, "99-practicum.md")))
        if err:
            errors.append("99-practicum.md: " + err)
        else:
            if pmeta.get("kind") != "practicum-spec":
                errors.append("99-practicum.md: kind must be 'practicum-spec'")
            if slug and pmeta.get("course") != slug:
                errors.append("99-practicum.md: course must be '%s'" % slug)
            if not pmeta.get("title"):
                errors.append("99-practicum.md: title is missing")
            pconcepts = as_list(pmeta, "concepts")
            if not pconcepts:
                errors.append("99-practicum.md: concepts must be a non-empty list")
            for cid in pconcepts or []:
                if cid not in all_concepts:
                    errors.append("99-practicum.md: concept '%s' is not in the concept map" % cid)
            check_order(headings(strip_code(pbody), 2), PRACTICUM_HEADINGS, "99-practicum.md", errors)
            check_links("99-practicum.md", pbody, files, errors)

    # ---- progress.md (reserved; light check only) ------------------------
    if "progress.md" in files:
        gmeta, _, err = parse_frontmatter(read(os.path.join(course_dir, "progress.md")))
        if err or gmeta.get("kind") != "progress" or (slug and gmeta.get("course") != slug):
            errors.append("progress.md: expected frontmatter kind: progress, course: %s" % slug)

    summary = "OK: course '%s' - %d lessons, %d concepts, %d objectives" % (
        slug, len(nums), len(all_concepts), len(objectives))
    return errors, summary


def main(argv):
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    errors, summary = check_course(argv[1])
    if errors:
        for e in errors:
            print("FAIL " + e)
        print("%d problem(s)." % len(errors))
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
