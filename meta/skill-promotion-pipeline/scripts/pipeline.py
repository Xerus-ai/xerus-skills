#!/usr/bin/env python3
"""Deterministic gates for a skill-promotion pipeline.

Python 3 stdlib only. If PyYAML is installed it is used for strict YAML parsing;
without it a small line parser handles the subset this pipeline writes.

Every subcommand takes --root (default: current directory), the registry root.
Layout it reads and writes under the root:

  archive/objects/<id>/     immutable copies of captured skill trees
  archive/manifest.jsonl    one row per captured tree (origin, licence, size)
  archive/clusters.json     normalised name -> [object ids]
  archive/ratings.jsonl     optional: one rating row per cluster
  archive/cache/            derived shingle cache for `overlap` (safe to delete)
  decisions.jsonl           append-only decision ledger (one row per cluster per batch)
  registry-index.json       generated index of curated skills
  work/                     batch working files (ignored by discovery)
  <any>/<skill>/SKILL.md    curated skills, each with an optional skill.yaml sidecar

Subcommands:
  capture SRC --origin LABEL  archive every skill tree under SRC (idempotent)
  clusters                    group archived trees by normalised name
  status [--list STATUS]      per-cluster coverage: ledger verdict > cited source > open
  ledger-append FILE --batch B  validate one batch's decisions and append them
  provenance [--deep]         every cited archive file exists; fails if nothing was checked
  index                       rebuild registry-index.json from SKILL.md frontmatter
  overlap SKILL_DIR           word n-gram overlap vs cited sources and every unclear-licence archive file

Relative FILE / SKILL_DIR arguments are tried against the current directory, then against --root.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter

try:
    import yaml  # optional
except ImportError:
    yaml = None

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}
NOT_SKILLS = {"archive", "work"}  # top-level folders that never hold curated skills
LICENCE_PREFIXES = ("license", "licence", "copying")
# Restrictive and source-available licences first: several exist precisely to sit on top of OSI text
# (Commons Clause, SSPL), so a permissive match is never the last word. Rules are tried on the title
# region first, because full GPLv3 and MPL-2.0 texts both name the Affero GPL in their body.
LICENCE_RULES = [
    ("ELv2", "elastic license"),
    ("BUSL", "business source license"),
    ("SSPL", "server side public license"),
    ("Commons-Clause", "commons clause"),
    ("PolyForm", "polyform"),
    ("FSL", "functional source license"),
    ("SUL", "sustainable use license"),
    ("Confluent", "confluent community license"),
    ("AGPL", "gnu affero general public license"),
    ("LGPL", "gnu lesser general public license"),
    ("GPL", "gnu general public license"),
    ("MPL-2.0", "mozilla public license"),
    ("Apache-2.0", "apache license"),
    ("MIT", "permission is hereby granted, free of charge"),
    ("BSD", "redistribution and use in source and binary forms"),
    ("ISC", "permission to use, copy, modify, and/or distribute"),
    ("CC", "creative commons"),
]
PERMISSIVE = {"MIT", "Apache-2.0", "BSD", "ISC"}
GPL_FAMILY = {"AGPL", "LGPL", "GPL"}
VERDICTS = ("new", "merge", "skip")
ARCHIVE_CITE = re.compile(r"^archive/objects/([0-9a-f]{12})/(.+)$")


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def paths(root):
    a = os.path.join(root, "archive")
    return {
        "objects": os.path.join(a, "objects"),
        "cache": os.path.join(a, "cache"),
        "manifest": os.path.join(a, "manifest.jsonl"),
        "clusters": os.path.join(a, "clusters.json"),
        "ratings": os.path.join(a, "ratings.jsonl"),
        "ledger": os.path.join(root, "decisions.jsonl"),
        "index": os.path.join(root, "registry-index.json"),
    }


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as e:
                    die("%s line %d is not JSON (%s)" % (path, n, e))
    return rows


def append_jsonl(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def resolve(a, path, kind):
    """A relative path is tried against the current directory first, then against --root."""
    for cand in (os.path.abspath(path), os.path.join(a.root, path)):
        if (os.path.isdir(cand) if kind.endswith("folder") else os.path.isfile(cand)):
            return cand
    die("%s not found: %s (tried the current directory and --root %s)" % (kind, path, a.root))


def norm(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-") or "unnamed"


# ---------- YAML-ish parsing ----------

def parse_simple_yaml(text):
    """Top-level `key: value` scalars, `- item` block lists and one-line `[a, b]` flow lists.
    Nested mappings are ignored."""
    data, key = {}, None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("- ") and key is not None:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(s[2:].strip().strip("'\""))
        elif not line[0].isspace() and ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if val.startswith("[") and val.endswith("]"):
                data[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            else:
                data[key] = val.strip("'\"") if val else None
    return data


def load_meta(path):
    if not os.path.isfile(path):
        return {}
    text = read_text(path)
    if yaml:
        try:
            d = yaml.safe_load(text)
        except yaml.YAMLError as e:
            die("%s is not valid YAML (%s)" % (path, str(e).splitlines()[0]))
        return d if isinstance(d, dict) else {}
    return parse_simple_yaml(text)


def simple_frontmatter(block):
    d, lines, i = {}, block.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val[:1] in (">", "|"):
            body = []
            while i < len(lines) and (not lines[i].strip() or lines[i][0].isspace()):
                body.append(lines[i].strip())
                i += 1
            d[key] = " ".join(b for b in body if b) if val[0] == ">" else "\n".join(body).strip()
        elif val[:1] in ("'", '"'):
            d[key] = val[1:-1] if len(val) > 1 and val[-1] == val[0] else val
        else:
            if ": " in val:
                return None, "unquoted ': ' in `%s` (strict YAML rejects it; double-quote the value)" % key
            d[key] = val
    return d, None


def frontmatter(path):
    text = read_text(path)
    m = re.match(r"^---\r?\n(.*?)\r?\n---[ \t]*(\r?\n|$)", text, re.S)
    if not m:
        return None, "no YAML frontmatter"
    block = m.group(1)
    if yaml:
        try:
            d = yaml.safe_load(block)
        except yaml.YAMLError as e:
            return None, "frontmatter is not valid YAML (%s)" % str(e).splitlines()[0]
        if not isinstance(d, dict):
            return None, "frontmatter is not a mapping"
        return d, None
    return simple_frontmatter(block)


# ---------- archive helpers ----------

def walk_files(tree):
    out = []
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in filenames:
            full = os.path.join(dirpath, f)
            if os.path.isfile(full):
                out.append(os.path.relpath(full, tree).replace(os.sep, "/"))
    return sorted(out)


def tree_id(tree, files):
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode("utf-8") + b"\0")
        with open(os.path.join(tree, rel), "rb") as fh:
            h.update(fh.read())
        h.update(b"\0")
    return h.hexdigest()[:12]


def find_trees(src, marker):
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if marker in filenames:
            yield dirpath


def git_root(path):
    d = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def find_licence_file(tree, stop):
    """Nearest licence file walking UP from the tree itself, so a bundled third-party
    tree that carries its own licence wins over the pack's root licence."""
    d, stop = os.path.abspath(tree), os.path.abspath(stop)
    while True:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            names = []
        for n in names:
            if n.lower().startswith(LICENCE_PREFIXES) and os.path.isfile(os.path.join(d, n)):
                return os.path.join(d, n)
        parent = os.path.dirname(d)
        if d == stop or parent == d:
            return None
        d = parent


def classify_licence(text):
    """Title region first (full GPLv3 / MPL-2.0 texts name the Affero GPL in their body), but
    fail closed: a permissive text that names any restrictive licence anywhere in the file (an MIT
    pack with an Elastic-licensed directory, BSD code bundling GPL text) returns
    `mixed:<permissive>+<restrictive...>`, which is never clear."""
    t = " ".join(text.lower().split())

    def first(region):
        return next((label for label, needle in LICENCE_RULES if needle in region), None)

    named = [label for label, needle in LICENCE_RULES if needle in t]
    permissive = [label for label in named if label in PERMISSIVE]
    restrictive = []
    for label in named:
        if label not in PERMISSIVE:
            # GPLv3 names the AGPL and LGPL in its own body, so the variants read as one family here.
            label = "GPL-family" if label in GPL_FAMILY else label
            if label not in restrictive:
                restrictive.append(label)
    head = first(t[:600])
    if head in PERMISSIVE or (head is None and permissive):
        base = head or permissive[0]
        # Fail closed: a permissive text that also names a restrictive licence is mixed, never clear.
        return "mixed:%s+%s" % (base, "+".join(restrictive)) if restrictive else base
    if head or named:
        return head or named[0]
    if "all rights reserved" in t:
        return "proprietary"
    return "unknown"


# ---------- curated side ----------

def curated_skills(root):
    """Every folder holding a SKILL.md (the file every member has; a sidecar is optional)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel == ".":
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and d not in NOT_SKILLS)
            continue
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if "SKILL.md" in filenames:
            found.append(rel)
            dirnames[:] = []  # nested SKILL.md files belong to this skill
    return found


def cited_sources(root):
    """(skill, source string) for every `sources:` entry of every curated skill."""
    out = []
    for rel in curated_skills(root):
        meta = load_meta(os.path.join(root, rel, "skill.yaml"))
        for s in meta.get("sources") or []:
            out.append((rel, str(s).strip()))
    return out


def load_clusters(p, required=True):
    if not os.path.exists(p["clusters"]):
        if required:
            die("archive/clusters.json not found - run `clusters` first")
        return {}
    with open(p["clusters"], encoding="utf-8") as fh:
        return json.load(fh)


# ---------- subcommands ----------

def cmd_capture(a):
    root, p = a.root, paths(a.root)
    src = os.path.abspath(a.src)
    if not os.path.isdir(src):
        die("source folder not found: %s" % a.src)
    manifest = read_jsonl(p["manifest"])
    known = {r["id"] for r in manifest}
    stop = git_root(src) or src
    new, skipped, stubs = [], 0, 0
    today = datetime.date.today().isoformat()
    for tree in find_trees(src, a.marker):
        files = walk_files(tree)
        size = sum(os.path.getsize(os.path.join(tree, f)) for f in files)
        oid = tree_id(tree, files)
        if oid in known:
            skipped += 1
            continue
        lic_file = find_licence_file(tree, stop)
        licence = classify_licence(read_text(lic_file)) if lic_file else "none"
        name = os.path.basename(tree)
        if a.marker == "SKILL.md":
            fm, _ = frontmatter(os.path.join(tree, "SKILL.md"))
            if fm and fm.get("name"):
                name = str(fm["name"])
        marker_bytes = os.path.getsize(os.path.join(tree, a.marker))
        stubs += marker_bytes < 200
        stored = size <= a.max_bytes
        row = {
            "id": oid, "name": name, "origin": a.origin,
            "source": os.path.relpath(tree, src).replace(os.sep, "/"),
            "licence": licence, "licence_clear": licence in PERMISSIVE,
            "licence_file": os.path.relpath(lic_file, stop).replace(os.sep, "/") if lic_file else None,
            "files": len(files), "bytes": size, "marker_bytes": marker_bytes,
            "stored": stored, "captured_at": today,
        }
        if stored and not a.dry_run:
            dest = os.path.join(p["objects"], oid)
            for rel in files:
                target = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(os.path.join(tree, rel), target)
        known.add(oid)
        new.append(row)
    if not a.dry_run and new:
        append_jsonl(p["manifest"], new)
    lic = Counter(r["licence"] for r in new)
    print("trees found: %d  new: %d  already archived: %d  not stored (> %d bytes): %d"
          % (len(new) + skipped, len(new), skipped, a.max_bytes, sum(not r["stored"] for r in new)))
    print("licences of new rows: " + (", ".join("%s %d" % kv for kv in sorted(lic.items())) or "-"))
    if stubs:
        print("possible stubs (marker file < 200 bytes): %d - read them before rating" % stubs)
    if a.dry_run:
        print("dry run: nothing written")


def cmd_clusters(a):
    p = paths(a.root)
    manifest = read_jsonl(p["manifest"])
    if not manifest:
        die("archive/manifest.jsonl is empty - capture something first")
    clusters = {}
    for r in manifest:
        clusters.setdefault(norm(r["name"]), []).append(r["id"])
    clusters = {k: sorted(v) for k, v in sorted(clusters.items())}
    write_json(p["clusters"], clusters)
    multi = sum(len(v) > 1 for v in clusters.values())
    print("%d objects -> %d clusters (%d with more than one member)" % (len(manifest), len(clusters), multi))
    print("reminder: a name cluster can hold unrelated skills - triage reads the bodies and may split it")


def cmd_status(a):
    root, p = a.root, paths(a.root)
    clusters = load_clusters(p)
    manifest = {r["id"]: r for r in read_jsonl(p["manifest"])}
    decided = {}
    for r in read_jsonl(p["ledger"]):
        decided[r["cluster"]] = r  # append-only: a later batch's row supersedes an earlier one
    cited = {}
    for rel, s in cited_sources(root):
        m = ARCHIVE_CITE.match(s)
        if m:
            cited.setdefault(m.group(1), rel)
    ratings = {r.get("cluster"): r for r in read_jsonl(p["ratings"])}
    counts, rows = Counter(), []
    for c, ids in clusters.items():
        # Explicit precedence: ledger verdict > an archived member cited by a curated skill > open.
        if c in decided:
            d = decided[c]
            status = "skipped" if d["verdict"] == "skip" else "curated"
            where = d.get("target") or d.get("note") or ""
        elif any(i in cited for i in ids):
            status, where = "covered", next(cited[i] for i in ids if i in cited)
        else:
            status, where = "open", ""
        counts[status] += 1
        lic = sorted({manifest[i]["licence"] for i in ids if i in manifest})
        rt = ratings.get(c, {})
        rows.append((status, c, rt.get("quality"), rt.get("verdict"), "/".join(lic), where))
    print("clusters: %d  " % len(clusters) + "  ".join("%s %d" % kv for kv in sorted(counts.items())))
    if a.list:
        for status, c, q, v, lic, where in rows:
            if status == a.list:
                print("%-8s %-40s q=%-4s rated=%-7s licence=%-12s %s" % (status, c, q, v, lic, where))


def cmd_ledger_append(a):
    root, p = a.root, paths(a.root)
    with open(resolve(a, a.file, "decisions file"), encoding="utf-8") as fh:
        try:
            rows = json.load(fh)
        except json.JSONDecodeError as e:
            die("%s is not valid JSON (%s)" % (a.file, e))
    if not isinstance(rows, list) or not rows:
        die("%s must be a non-empty JSON list of decisions" % a.file)
    clusters = load_clusters(p)
    if any(r.get("batch") == a.batch for r in read_jsonl(p["ledger"])):
        die("batch %s is already in decisions.jsonl - the ledger is append-only; refusing to append twice" % a.batch)
    problems, seen = [], set()
    for i, r in enumerate(rows):
        c, v, t = r.get("cluster"), r.get("verdict"), r.get("target")
        tag = "row %d (%s)" % (i, c)
        if c not in clusters:
            problems.append("%s: cluster not in archive/clusters.json" % tag)
        if c in seen:
            problems.append("%s: cluster decided twice in one batch" % tag)
        seen.add(c)
        if v not in VERDICTS:
            problems.append("%s: verdict must be one of %s" % (tag, "/".join(VERDICTS)))
        if v in ("new", "merge") and (not t or not os.path.isfile(os.path.join(root, t, "SKILL.md"))):
            problems.append("%s: target %r has no SKILL.md - write the skill before logging it" % (tag, t))
        if v == "skip" and not str(r.get("note") or "").strip():
            problems.append("%s: a skip needs a reason in `note`" % tag)
    if problems:
        print("\n".join(problems))
        die("%d problem(s); nothing appended" % len(problems))
    date = a.date or datetime.date.today().isoformat()
    out = [{"cluster": r["cluster"], "verdict": r["verdict"],
            "target": r.get("target") if r["verdict"] != "skip" else None,
            "note": r.get("note"), "batch": a.batch, "date": date}
           for r in sorted(rows, key=lambda r: r["cluster"])]
    tally = Counter(r["verdict"] for r in out)
    print("batch %s: %d decisions (%s)" % (a.batch, len(out), ", ".join("%s %d" % kv for kv in sorted(tally.items()))))
    if a.dry_run:
        print("dry run: nothing appended")
        return
    append_jsonl(p["ledger"], out)
    print("appended to decisions.jsonl")


def cmd_provenance(a):
    root, p = a.root, paths(a.root)
    manifest = {r["id"]: r for r in read_jsonl(p["manifest"])}
    clusters = load_clusters(p, required=False)
    checked, urls, problems = 0, 0, []
    skills = curated_skills(root)
    for rel in skills:
        meta = load_meta(os.path.join(root, rel, "skill.yaml"))
        for s in meta.get("sources") or []:
            s = str(s).strip()
            if s.startswith(("http://", "https://")):
                urls += 1
                continue
            checked += 1
            m = ARCHIVE_CITE.match(s)
            if not m:
                problems.append("%s: source is neither archive/objects/<id>/<file> nor a URL: %s" % (rel, s))
                continue
            oid = m.group(1)
            if oid not in manifest:
                problems.append("%s: unknown object id %s" % (rel, oid))
            elif not manifest[oid].get("stored", True):
                problems.append("%s: object %s was never stored (too large at capture)" % (rel, oid))
            elif not glob.glob(os.path.join(root, s)):
                problems.append("%s: cited file does not exist: %s" % (rel, s))
        for c in meta.get("provenance") or []:
            if clusters and norm(c) not in clusters:
                problems.append("%s: provenance names an unknown cluster: %s" % (rel, c))
    for r in read_jsonl(p["ledger"]):
        t = r.get("target")
        if r.get("verdict") in ("new", "merge") and not os.path.isfile(os.path.join(root, str(t), "SKILL.md")):
            problems.append("decisions.jsonl: %s -> target %s has no SKILL.md" % (r.get("cluster"), t))
    deep = 0
    if a.deep:
        for oid, r in manifest.items():
            d = os.path.join(p["objects"], oid)
            if not r.get("stored", True):
                continue
            if not os.path.isdir(d):
                problems.append("archive: object %s is in the manifest but not on disk" % oid)
                continue
            deep += 1
            if tree_id(d, walk_files(d)) != oid:
                drop_cache(p, oid)
                problems.append("archive: object %s content changed since capture (the archive is immutable; "
                                "its overlap cache entry was dropped)" % oid)
    if checked == 0 and not a.allow_empty:
        problems.append("checked 0 archive citations - a gate that checks nothing is not a gate "
                        "(pass --allow-empty only for a registry with no archive-backed skills yet)")
    print("skills: %d  archive citations checked: %d  URL sources: %d%s  problems: %d"
          % (len(skills), checked, urls, "  objects re-hashed: %d" % deep if a.deep else "", len(problems)))
    if problems:
        print("\n".join(problems))
        sys.exit(1)


def cmd_index(a):
    root, p = a.root, paths(a.root)
    rows, problems = [], []
    for rel in curated_skills(root):
        fm, err = frontmatter(os.path.join(root, rel, "SKILL.md"))
        if err:
            problems.append("%s: %s" % (rel, err))
            continue
        name, desc = fm.get("name"), " ".join(str(fm.get("description") or "").split())
        folder = rel.rsplit("/", 1)[-1]
        if name != folder:
            problems.append("%s: frontmatter name %r != folder name %r" % (rel, name, folder))
        if not desc:
            problems.append("%s: empty description" % rel)
        elif len(desc) > 1024:
            problems.append("%s: description is %d chars (max 1024)" % (rel, len(desc)))
        meta = load_meta(os.path.join(root, rel, "skill.yaml"))
        rows.append({"path": rel, "name": name, "description": desc,
                     "version": meta.get("version"), "provenance": meta.get("provenance") or []})
    if not rows and not problems:
        die("no SKILL.md found under %s - refusing to write an empty index" % root)
    if problems:
        print("\n".join(problems))
        die("%d problem(s); registry-index.json NOT written" % len(problems))
    write_json(p["index"], {"count": len(rows), "skills": rows})
    print("registry-index.json: %d skills" % len(rows))


def shingle_map(text, n):
    """64-bit hash -> text of every n-word window (the text is kept to show evidence)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    out = {}
    for i in range(len(words) - n + 1):
        s = " ".join(words[i:i + n])
        out[int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")] = s
    return out


def text_or_none(path):
    """A file's text, or None if it looks binary (a NUL byte in the first 8 KB). Any extension
    counts: a cited .html or .csv source is compared like a .md one."""
    with open(path, "rb") as fh:
        data = fh.read()
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def cache_digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest()


def object_shingles(p, oid, n):
    """({file: set of shingle hashes}, current tree hash) for one archived object.

    Shingling is the expensive part, so it is cached in archive/cache/. The cheap part, the
    object's tree hash, is recomputed on EVERY call: a cache entry is used only if it was built
    from exactly the files on disk now and still matches its own digest. Anything else (object
    edited or restored since, hand-edited or truncated entry) is rebuilt, never trusted."""
    d = os.path.join(p["objects"], oid)
    files = walk_files(d)
    tree = tree_id(d, files)
    cache = os.path.join(p["cache"], "shingles-n%d" % n, oid + ".json")
    try:
        with open(cache, encoding="utf-8") as fh:
            entry = json.load(fh)
        if entry.get("tree") == tree and entry.get("digest") == cache_digest(entry.get("files")):
            return {k: set(v) for k, v in entry["files"].items()}, tree
    except (OSError, ValueError, AttributeError, TypeError):
        pass  # missing, truncated or malformed: rebuild below
    out = {}
    for rel in files:
        text = text_or_none(os.path.join(d, rel))
        if text is not None:
            out[rel] = sorted(set(shingle_map(text, n)))
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    tmp = cache + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"tree": tree, "digest": cache_digest(out), "files": out}, fh)
    os.replace(tmp, cache)  # an interrupted run never leaves a half-written entry
    return {k: set(v) for k, v in out.items()}, tree


def drop_cache(p, oid):
    for f in glob.glob(os.path.join(p["cache"], "shingles-n*", oid + ".json")):
        os.remove(f)


def evidence(mine_map, shared, k=2):
    return "; e.g. " + " | ".join('"%s"' % mine_map[h] for h in sorted(shared)[:k]) if shared else ""


def cmd_overlap(a):
    root, p = a.root, paths(a.root)
    skill = resolve(a, a.skill_dir, "skill folder")
    if not os.path.isfile(os.path.join(skill, "SKILL.md")):
        die("%s has no SKILL.md - not a skill folder" % a.skill_dir)
    meta = load_meta(os.path.join(skill, "skill.yaml"))
    manifest = {r["id"]: r for r in read_jsonl(p["manifest"])}
    problems, edited = [], set()

    def load(oid):
        shingled, tree = object_shingles(p, oid, a.n)
        if tree != oid and oid not in edited:
            edited.add(oid)
            problems.append("archive: object %s edited since capture - run provenance --deep "
                            "(compared against its files as they are now)" % oid)
        return shingled

    sources, urls = {}, 0
    for s in meta.get("sources") or []:
        s = str(s).strip()
        m = ARCHIVE_CITE.match(s)
        if not m:
            urls += s.startswith(("http://", "https://"))
            continue
        oid = m.group(1)
        clear = manifest.get(oid, {}).get("licence_clear", False)
        objdir = os.path.join(p["objects"], oid)
        if not os.path.isdir(objdir):
            continue
        cached = load(oid)
        for f in glob.glob(os.path.join(root, s)):
            rel = os.path.relpath(f, objdir).replace(os.sep, "/")
            if rel in cached:
                sources["archive/objects/%s/%s" % (oid, rel)] = (cached[rel], clear)
    # A writer who copies from a tree it was told not to copy from will not cite it, so every
    # stored archive file without a clear licence is compared too, cited or not.
    uncited = {}
    for oid, r in manifest.items():
        if r.get("licence_clear") or not r.get("stored", True) or not os.path.isdir(os.path.join(p["objects"], oid)):
            continue
        for rel, sh in load(oid).items():
            key = "archive/objects/%s/%s" % (oid, rel)
            if key not in sources:
                uncited[key] = (sh, r.get("licence"))
    if not sources and not uncited:
        die("nothing to compare: %s cites no archive files and the archive holds no unclear-licence files"
            % a.skill_dir)
    compared = 0
    for rel in walk_files(skill):
        text = text_or_none(os.path.join(skill, rel))
        if text is None or rel == "skill.yaml":
            continue
        mine_map = shingle_map(text, a.n)
        mine = set(mine_map)
        if len(mine) < 20:
            continue
        compared += 1
        best, against, clear, best_shared = 0.0, "-", True, set()
        for sp, (theirs, c) in sources.items():
            shared = mine & theirs
            pct = 100.0 * len(shared) / len(mine)
            if pct > best:
                best, against, clear, best_shared = pct, sp, c, shared
            if not c and pct > a.max_unclear:
                problems.append("%s: %.1f%% overlap with %s, whose licence is not clear%s"
                                % (rel, pct, sp, evidence(mine_map, shared)))
        if best > a.max:
            problems.append("%s: %.1f%% overlap with %s (max %.0f%%) - fold, don't paste%s"
                            % (rel, best, against, a.max, evidence(mine_map, best_shared)))
        worst_u, worst_key = 0.0, "-"
        for key, (theirs, lic) in uncited.items():
            shared = mine & theirs
            pct = 100.0 * len(shared) / len(mine)
            if pct > worst_u:
                worst_u, worst_key = pct, key
            if pct > a.max_unclear:
                problems.append("%s: %.1f%% uncited overlap with %s (licence not clear: %s)%s"
                                % (rel, pct, key, lic, evidence(mine_map, shared)))
        print("%6.1f%%  %s  (vs %s%s)  uncited unclear max %.1f%% (%s)"
              % (best, rel, against, "" if clear else ", licence NOT clear", worst_u, worst_key))
    if compared == 0:
        problems.append("compared 0 files - nothing in %s was long enough to check" % a.skill_dir)
    print("files compared: %d  cited archive files: %d  URL sources (not compared): %d  "
          "uncited unclear-licence archive files: %d  %d-word shingles  problems: %d"
          % (compared, len(sources), urls, len(uncited), a.n, len(problems)))
    if problems:
        print("\n".join(problems))
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=".", help="registry root (default: current directory)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture", help="archive every skill tree under SRC")
    c.add_argument("src")
    c.add_argument("--origin", required=True, help="where it came from: repo URL, pack name, or a label")
    c.add_argument("--marker", default="SKILL.md", help="file that marks a skill tree (default SKILL.md)")
    c.add_argument("--max-bytes", type=int, default=5_000_000, help="larger trees are recorded but not stored")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(fn=cmd_capture)

    c = sub.add_parser("clusters", help="group archived trees by normalised name")
    c.set_defaults(fn=cmd_clusters)

    c = sub.add_parser("status", help="per-cluster coverage")
    c.add_argument("--list", choices=["open", "covered", "curated", "skipped"])
    c.set_defaults(fn=cmd_status)

    c = sub.add_parser("ledger-append", help="validate and append one batch of decisions")
    c.add_argument("file", help="JSON list of {cluster, verdict, target, note}")
    c.add_argument("--batch", required=True)
    c.add_argument("--date", help="ISO date to record (default: today)")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(fn=cmd_ledger_append)

    c = sub.add_parser("provenance", help="check every cited archive file exists")
    c.add_argument("--deep", action="store_true", help="also re-hash every stored object")
    c.add_argument("--allow-empty", action="store_true")
    c.set_defaults(fn=cmd_provenance)

    c = sub.add_parser("index", help="rebuild registry-index.json")
    c.set_defaults(fn=cmd_index)

    c = sub.add_parser("overlap", help="n-gram overlap vs cited sources and all unclear-licence archive files")
    c.add_argument("skill_dir")
    c.add_argument("--n", type=int, default=8, help="shingle size in words (default 8)")
    c.add_argument("--max", type=float, default=25.0, help="max %% per file vs a permissive source")
    c.add_argument("--max-unclear", type=float, default=2.0, help="max %% per file vs a source without a clear licence")
    c.set_defaults(fn=cmd_overlap)

    a = ap.parse_args()
    a.root = os.path.abspath(a.root)
    a.fn(a)


if __name__ == "__main__":
    main()
