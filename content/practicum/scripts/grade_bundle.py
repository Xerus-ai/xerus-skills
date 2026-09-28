#!/usr/bin/env python3
"""Assemble the blind-grading bundle for a practicum.

The grader must see only evidence: the course's practicum spec, the
orchestration rubric, the record's Task / Acceptance criteria / Decision log
sections, the artifact (diff or files) and the raw acceptance-check output.
Everything else in the record (Result, Grade, notes) is left out on purpose.

Python 3 stdlib only. Examples:

  python grade_bundle.py --spec course/practicum-spec.md \
      --record practicum/attempt-01.md --git-base abc123 \
      --check-output practicum/attempt-01/check-1.txt \
      --out practicum/attempt-01/grade-bundle.md

  python grade_bundle.py --spec course/practicum-spec.md \
      --record practicum/attempt-01.md --files sandbox/tool.py sandbox/README.md \
      --check-output practicum/attempt-01/check-1.txt --out bundle.md

Exit codes: 0 bundle written; 1 bundle written with warnings (printed to
stderr, also stated inside the bundle); 2 usage error or missing input.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

RUBRIC = Path(__file__).resolve().parent.parent / "references" / "orchestration-rubric.md"
KEEP_SECTIONS = ("task", "acceptance criteria", "decision log")
MAX_CHARS = 200_000  # per included item; truncation is announced to the grader


def fail(msg):
    print(f"grade_bundle: {msg}", file=sys.stderr)
    sys.exit(2)


def read(path):
    p = Path(path)
    if not p.is_file():
        fail(f"not a file: {path}")
    return p.read_text(encoding="utf-8", errors="replace")


def cap(text, label, warnings):
    if len(text) <= MAX_CHARS:
        return text
    warnings.append(f"{label} truncated to {MAX_CHARS} chars; treat anything it should show as unverified")
    return text[:MAX_CHARS] + f"\n\n[TRUNCATED: {label} exceeded {MAX_CHARS} chars]\n"


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def record_sections(text):
    """Return {lower-cased H2 title: body} for the H2 sections of the record."""
    sections, title, buf = {}, None, []
    for line in strip_frontmatter(text).splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if title is not None:
                sections[title] = "\n".join(buf).strip()
            title, buf = m.group(1).strip().lower(), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        sections[title] = "\n".join(buf).strip()
    return sections


def git_toplevel(where):
    try:
        out = subprocess.run(["git", "-C", str(where), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=False)
    except FileNotFoundError:
        fail("git not found; pass --diff-file or --files instead")
    return out.stdout.strip() if out.returncode == 0 else ""


def git_diff(repo, base, paths, excludes):
    """Diff plus untracked files, never including the practicum's own files.

    The record (with its Result/Grade sections), the bundle and the course's
    progress.md (the practicum log entries) would leak the narrative.
    """
    top = git_toplevel(repo)
    specs = list(paths) or ["."]
    for d in excludes:
        try:
            rel = Path(d).resolve().relative_to(Path(top).resolve()).as_posix() if top else None
        except ValueError:
            rel = None  # outside the repo: git cannot see it anyway
        if rel:
            specs.append(f":(top,exclude){rel}")
    paths = specs
    cmd = ["git", "-C", repo, "diff", base, "--"] + list(paths)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", check=False)
    except FileNotFoundError:
        fail("git not found; pass --diff-file or --files instead")
    if out.returncode != 0:
        fail(f"git diff failed: {out.stderr.strip()}")
    # Untracked files are invisible to git diff; list them so the grader knows.
    st = subprocess.run(["git", "-C", repo, "ls-files", "--others", "--exclude-standard", "--"] + list(paths),
                        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return out.stdout, [l for l in st.stdout.splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True, help="the course's practicum spec (artifact rubric)")
    ap.add_argument("--record", required=True, help="the practicum record file")
    ap.add_argument("--lesson", action="append", default=[], help="optional short lesson/principles file (repeatable)")
    art = ap.add_mutually_exclusive_group(required=True)
    art.add_argument("--git-base", help="git ref the build started from; bundle includes `git diff REF`")
    art.add_argument("--diff-file", help="a saved diff or patch file")
    art.add_argument("--files", nargs="+", help="artifact files to include whole (greenfield work)")
    ap.add_argument("--repo", help="repository for --git-base (default: the git repo containing --record)")
    ap.add_argument("--path", action="append", default=[], help="limit --git-base diff to this path, relative to --repo (repeatable)")
    ap.add_argument("--check-output", action="append", default=[], help="raw acceptance-check output file (repeatable)")
    ap.add_argument("--out", required=True, help="where to write the bundle")
    a = ap.parse_args()

    warnings = []
    sections = record_sections(read(a.record))
    kept = {k: sections.get(k, "") for k in KEEP_SECTIONS}
    for k, v in kept.items():
        if not v:
            warnings.append(f"record section '## {k}' is missing or empty")
    log_entries = [l for l in kept["decision log"].splitlines() if re.match(r"^\s*-\s*\S", l)]
    if len(log_entries) < 3:
        warnings.append(f"decision log has {len(log_entries)} entries; most orchestration dimensions will be unevidenced")

    parts = ["# Practicum grading bundle",
             "Everything the grader may see is below. Nothing else about the session is available.",
             ""]

    parts += ["## 1. Practicum spec (artifact rubric)", "", cap(strip_frontmatter(read(a.spec)), "spec", warnings), ""]
    for i, lesson in enumerate(a.lesson, 1):
        parts += [f"## 1.{i} Lesson / principles: {Path(lesson).name}", "",
                  cap(strip_frontmatter(read(lesson)), f"lesson {lesson}", warnings), ""]

    if not RUBRIC.is_file():
        fail(f"orchestration rubric missing next to this script: {RUBRIC}")
    parts += ["## 2. Orchestration rubric", "", strip_frontmatter(RUBRIC.read_text(encoding="utf-8")), ""]

    parts += ["## 3. Practicum record (build-time sections only)", ""]
    for k in KEEP_SECTIONS:
        parts += [f"### {k.capitalize()}", "", kept[k] or "(missing)", ""]

    parts += ["## 4. Artifact", ""]
    if a.git_base:
        if not a.repo:
            a.repo = git_toplevel(Path(a.record).resolve().parent)
            if not a.repo:
                fail("--record is not inside a git repository; pass --repo, --diff-file or --files")
        record_dir = Path(a.record).resolve().parent
        excludes = {record_dir, Path(a.out).resolve().parent}
        if (record_dir.parent / "progress.md").is_file():
            excludes.add(record_dir.parent / "progress.md")
        diff, untracked = git_diff(a.repo, a.git_base, a.path, excludes)
        if not diff.strip() and not untracked:
            warnings.append(f"git diff {a.git_base} is empty; nothing was built, or the wrong base/path was given")
        parts += [f"`git diff {a.git_base}`" + (f" limited to {', '.join(a.path)}" if a.path else ""), "",
                  "```diff", cap(diff, "diff", warnings), "```", ""]
        if untracked:
            parts += ["Untracked new files (not in the diff above; contents follow):", ""]
            for rel in untracked:
                f = Path(a.repo) / rel  # ls-files paths are relative to --repo
                body = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else "(unreadable)"
                parts += [f"#### {rel}", "", "```", cap(body, rel, warnings), "```", ""]
    elif a.diff_file:
        parts += [f"Patch file: {Path(a.diff_file).name}", "", "```diff",
                  cap(read(a.diff_file), "diff file", warnings), "```", ""]
    else:
        for f in a.files:
            parts += [f"#### {f}", "", "```", cap(read(f), f, warnings), "```", ""]

    parts += ["## 5. Acceptance-check output (raw, as captured)", ""]
    if not a.check_output:
        warnings.append("no acceptance-check output supplied; every runnable criterion must be graded unverified")
        parts += ["NO ACCEPTANCE-CHECK OUTPUT WAS PROVIDED. Criteria that need a run are unverified.", ""]
    for c in a.check_output:
        parts += [f"#### {Path(c).name}", "", "```", cap(read(c), c, warnings), "```", ""]

    if warnings:
        parts += ["## Bundle warnings", ""] + [f"- {w}" for w in warnings] + [""]

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    print(f"grade_bundle: wrote {out} ({out.stat().st_size} bytes, {len(log_entries)} decision-log entries)")
    for w in warnings:
        print(f"grade_bundle: WARNING {w}", file=sys.stderr)
    sys.exit(1 if warnings else 0)


if __name__ == "__main__":
    main()
