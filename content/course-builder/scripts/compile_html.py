#!/usr/bin/env python3
"""Compile a course folder into one self-contained HTML file (course.html).

Usage:
    python compile_html.py <course-dir> [--out <file>]

Reads index.md, the lessons 01..NN and 99-practicum.md (never assessment.md or
progress.md) and writes a single file with inline CSS, no scripts, and no
external requests. Links between course files become in-page anchors.
Python 3 stdlib only. Handles the Markdown subset course-builder writes:
headings, paragraphs, bullet and numbered lists (nested by indentation),
fenced code, blockquotes, pipe tables, **bold**, *italic*, `code`, links.
"""
import html
import os
import re
import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_course import LESSON_FILE_RE, parse_frontmatter, read  # noqa: E402

CSS = """
:root { --ink:#1d1c1a; --soft:#5d5a54; --rule:#dcd6cb; --paper:#fbf9f4; --tint:#f1ede4; --accent:#8a3b12; }
* { box-sizing:border-box; }
html { background:var(--paper); color:var(--ink); }
body { margin:0; font:17px/1.65 Charter,"Bitstream Charter","Iowan Old Style",Georgia,serif; }
main { max-width:44rem; margin:0 auto; padding:3rem 1.25rem 6rem; }
header.cover { border-bottom:2px solid var(--ink); padding-bottom:1.5rem; margin-bottom:2rem; }
header.cover h1 { font-size:2.3rem; line-height:1.15; margin:0 0 .6rem; letter-spacing:-.01em; }
.meta { color:var(--soft); font:14px/1.5 ui-sans-serif,system-ui,sans-serif; }
nav.toc { font:15px/1.6 ui-sans-serif,system-ui,sans-serif; background:var(--tint); padding:1rem 1.25rem; margin:0 0 3rem; }
nav.toc ol { margin:.3rem 0 0; padding-left:1.4rem; }
nav.toc a { color:var(--ink); }
section.part { border-top:1px solid var(--rule); padding-top:2rem; margin-top:3rem; }
.kicker { font:600 12px/1 ui-sans-serif,system-ui,sans-serif; letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }
h1,h2,h3 { line-height:1.25; }
section.part h1 { font-size:1.8rem; margin:.4rem 0 1rem; }
h2 { font-size:1.3rem; margin-top:2.2rem; }
h3 { font-size:1.08rem; margin-top:1.6rem; }
a { color:var(--accent); }
code { font:.88em ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; background:var(--tint); padding:.08em .3em; }
pre { background:var(--tint); padding:1rem; overflow-x:auto; line-height:1.45; }
pre code { background:none; padding:0; }
blockquote { margin:1rem 0; padding-left:1rem; border-left:3px solid var(--rule); color:var(--soft); }
table { border-collapse:collapse; width:100%; font-size:.95em; }
th,td { border-bottom:1px solid var(--rule); padding:.4rem .5rem; text-align:left; vertical-align:top; }
@media print { nav.toc { display:none; } section.part { break-before:page; border:0; } }
"""


def anchor_for(target):
    target = target.split("#")[0]
    if target == "index.md":
        return "#course"
    if target == "99-practicum.md":
        return "#practicum"
    m = LESSON_FILE_RE.match(target)
    return "#lesson-%s" % m.group(1) if m else None


def inline(text):
    # Pull code spans out first so nothing inside them is formatted.
    spans = []

    def keep(m):
        spans.append("<code>%s</code>" % html.escape(m.group(1)))
        return "\x00%d\x00" % (len(spans) - 1)

    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=False)

    def link(m):
        label, target = m.group(1), m.group(2)  # target is already HTML-escaped (quote=False)
        if re.match(r"^(https?:|mailto:|#)", target, re.I):
            href = target  # external links, including .md URLs such as a GitHub README
        elif target.endswith(".md") or ".md#" in target:
            href = anchor_for(target)  # scheme-less sibling course file -> in-page anchor
        else:
            href = None  # javascript:, data:, stray relative paths: render as plain text
        if not href:
            return label
        return '<a href="%s">%s</a>' % (href.replace('"', "&quot;"), label)

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def render_list(lines):
    """Render consecutive list lines (possibly nested by indentation) to HTML."""
    out, stack = [], []  # stack of (indent, tag)
    for line in lines:
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if not m:  # continuation line of the previous item
            out.append(" " + inline(line.strip()))
            continue
        indent, marker, content = len(m.group(1)), m.group(2), m.group(3)
        tag = "ul" if marker in "-*+" else "ol"
        while stack and indent < stack[-1][0]:
            out.append("</li></%s>" % stack.pop()[1])
        if stack and indent == stack[-1][0]:
            out.append("</li>")
        elif not stack or indent > stack[-1][0]:
            out.append("<%s>" % tag)
            stack.append((indent, tag))
        out.append("<li>" + inline(content))
    while stack:
        out.append("</li></%s>" % stack.pop()[1])
    return "".join(out)


def render_table(lines):
    def cells(line):
        return [c.strip() for c in line.strip().strip("|").split("|")]

    head, rows = cells(lines[0]), [cells(l) for l in lines[2:]]
    out = ["<table><thead><tr>"] + ["<th>%s</th>" % inline(c) for c in head] + ["</tr></thead><tbody>"]
    for r in rows:
        out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def markdown(body, shift=0):
    """Markdown subset -> HTML. shift demotes headings (shift=0 keeps levels)."""
    lines, out, i = body.split("\n"), [], 0
    is_list = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.lstrip().startswith("```"):
            code, i = [], i + 1
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code)))
            i += 1
        elif re.match(r"^#{1,6} ", line):
            level = min(6, len(line.split(" ")[0]) + shift)
            out.append("<h%d>%s</h%d>" % (level, inline(line.split(" ", 1)[1].strip()), level))
            i += 1
        elif line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % markdown("\n".join(quote), shift))
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(render_table(rows))
        elif is_list.match(line):
            items = []
            while i < len(lines) and lines[i].strip() and (is_list.match(lines[i]) or lines[i].startswith("  ")):
                items.append(lines[i])
                i += 1
            out.append(render_list(items))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6} |```|>|\s*\|)", lines[i]) \
                    and not is_list.match(lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>%s</p>" % inline(" ".join(para)))
    return "\n".join(out)


def drop_title(body):
    """Remove the first '# ' heading; the compiler renders its own section titles."""
    return re.sub(r"^\s*# .*\n?", "", body, count=1)


def compile_course(course_dir):
    meta, body, err = parse_frontmatter(read(os.path.join(course_dir, "index.md")))
    if err:
        raise SystemExit("index.md: " + err)
    title = meta.get("title", "Course")
    lessons = sorted(f for f in os.listdir(course_dir)
                     if LESSON_FILE_RE.match(f) and f[:2] not in ("00", "99"))
    parts, toc = [], []
    for f in lessons:
        lmeta, lbody, err = parse_frontmatter(read(os.path.join(course_dir, f)))
        if err:
            raise SystemExit("%s: %s" % (f, err))
        num = f[:2]
        ltitle = lmeta.get("title", f)
        mins = lmeta.get("est_minutes")
        toc.append('<li><a href="#lesson-%s">%s</a></li>' % (num, html.escape(ltitle)))
        parts.append('<section class="part" id="lesson-%s"><div class="kicker">Lesson %s%s</div>'
                     "<h1>%s</h1>%s</section>" % (
                         num, int(num), " &middot; %s min" % html.escape(mins) if mins else "",
                         html.escape(ltitle), markdown(drop_title(lbody))))
    practicum = os.path.join(course_dir, "99-practicum.md")
    if os.path.exists(practicum):
        pmeta, pbody, err = parse_frontmatter(read(practicum))
        if err:
            raise SystemExit("99-practicum.md: " + err)
        toc.append('<li><a href="#practicum">Practicum</a></li>')
        parts.append('<section class="part" id="practicum"><div class="kicker">Practicum</div>'
                     "<h1>%s</h1>%s</section>" % (html.escape(pmeta.get("title", "Practicum")),
                                                  markdown(drop_title(pbody))))
    facts = [x for x in (meta.get("level"), "%d lessons" % len(lessons),
                         "updated %s" % meta["updated"] if meta.get("updated") else None) if x]
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title><style>%s</style></head>
<body><main>
<header class="cover" id="course"><div class="kicker">Course</div><h1>%s</h1>
<p>%s</p><div class="meta">%s</div></header>
<nav class="toc"><strong>Contents</strong><ol>%s</ol></nav>
<section id="overview">%s</section>
%s
</main></body></html>
""" % (html.escape(title), CSS, html.escape(title), inline(meta.get("summary", "")),
       html.escape(" / ".join(facts)), "".join(toc), markdown(drop_title(body)), "\n".join(parts))


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    course_dir, out = args[0], os.path.join(args[0], "course.html")
    if "--out" in args:
        out = args[args.index("--out") + 1]
    page = compile_course(course_dir)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("wrote %s (%d bytes)" % (out, len(page.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
