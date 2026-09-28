#!/usr/bin/env python3
"""workspace-cleanup helper. Python 3 standard library only; git is optional.

Subcommands:
  inventory ROOT   one row per entry (size, files, newest mtime, git state, last commit, refs)
  refs TARGET      every text file that mentions TARGET (several spellings of the path)
  hash PATH        stable content hash of a file or tree (byte-identical proof)
  log              append a write-ahead manifest row (intent before acting, done after)
  check MANIFEST   verify every manifest row against the disk + re-scan for stale references

Exit codes: 0 ok, 1 check failed / refused, 2 usage error.
"""
import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

SKIP_DIRS = {".git", ".hg", ".svn"}
SCAN_SKIP_DIRS = SKIP_DIRS | {"node_modules", "__pycache__", ".venv", "venv", ".tox",
                              ".mypy_cache", ".pytest_cache", "dist", "build", ".next"}
MAX_SCAN_BYTES = 1_000_000
CLEANUP_DIR = ".cleanup"


def posix(p):
    return p.replace(os.sep, "/")


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def walk_files(path, skip=SKIP_DIRS):
    """Yield file paths under path (or path itself if it is a file). Symlinks are not followed."""
    if os.path.isfile(path) or os.path.islink(path):
        yield path
        return
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for f in sorted(filenames):
            yield os.path.join(dirpath, f)


def excluded(rel, patterns):
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel.split("/")[0], p) for p in patterns)


# ---------------------------------------------------------------- git (optional)

def git(root, *args):
    if not shutil.which("git"):
        return None
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def in_git(root):
    return git(root, "rev-parse", "--is-inside-work-tree") is not None


def git_state_counts(root, depth):
    """Count tracked / untracked / ignored paths per ancestor prefix (up to depth)."""
    out = {}
    queries = {
        "tracked": ["ls-files", "-z"],
        "untracked": ["ls-files", "-z", "--others", "--exclude-standard", "--directory"],
        "ignored": ["ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"],
    }
    for state, args in queries.items():
        counts = Counter()
        for p in (git(root, *args) or "").split("\0"):
            p = p.rstrip("/")
            if not p:
                continue
            parts = p.split("/")
            for i in range(1, min(len(parts), depth) + 1):
                counts["/".join(parts[:i])] += 1
        out[state] = counts
    return out


def git_label(rel, counts):
    if counts is None:
        return "no-git"
    parts = rel.split("/")
    # an untracked/ignored ancestor directory covers everything below it
    for state in ("ignored", "untracked"):
        for i in range(1, len(parts)):
            if counts[state].get("/".join(parts[:i])) and not counts["tracked"].get("/".join(parts[:i])):
                return state
    found = [s for s in ("tracked", "untracked", "ignored") if counts[s].get(rel)]
    return "+".join(found) if found else "unknown"


# ---------------------------------------------------------------- reference scan

def default_excludes(root):
    """Never scanned for references: cleanup records (.cleanup/, they are history by design) and this
    skill's own folder if it is installed inside the root (its docs mention example paths)."""
    out = [CLEANUP_DIR + "/*"]
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        rel = os.path.relpath(skill_dir, os.path.abspath(root))
    except ValueError:  # different drive
        return out
    if not rel.startswith(os.pardir):
        out.append(posix(rel) + "/*")
    return out


def text_files(root, excludes):
    excludes = list(excludes) + default_excludes(root)
    for path in walk_files(root, SCAN_SKIP_DIRS):
        rel = posix(os.path.relpath(path, root))
        if excluded(rel, excludes):
            continue
        try:
            if os.path.getsize(path) > MAX_SCAN_BYTES:
                continue
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue
        yield rel, data.decode("utf-8", "replace")


def path_kind(root, target):
    p = os.path.join(root, target)
    return "dir" if os.path.isdir(p) and not os.path.islink(p) else "file"


def spellings(root, target, kind=None):
    """The ways a path tends to be written. Returns (relative_forms, absolute_forms).

    Relative forms are the repo-relative path in both slash styles. The one exception is a top-level
    DIRECTORY ("docs"): its bare name is ordinary prose ("read the docs"), so it only matches
    path-shaped (docs/  docs\\  quoted "docs" 'docs' `docs`, or right after a separator, see
    ref_matcher); bare-word matching is opt-in
    (refs --basename). Files ("SETUP.md", "Makefile") match by plain name. kind is "file" or "dir";
    pass it when the target no longer exists (after a move), otherwise it is read from disk."""
    kind = kind or path_kind(root, target)
    absolute = os.path.abspath(target if os.path.isabs(target) else os.path.join(root, target))
    rel = posix(os.path.relpath(absolute, os.path.abspath(root)))
    if not rel or rel == ".":
        return [], []
    if "/" in rel or kind != "dir":
        rel_forms = {rel, rel.replace("/", "\\")}
    else:
        rel_forms = {rel + "/", rel + "\\", f'"{rel}"', f"'{rel}'", f"`{rel}`"}
    return sorted(rel_forms), sorted({absolute, posix(absolute)})


HEAD = r"(?<![A-Za-z0-9_-])"
TAIL = r"(?![A-Za-z0-9_-])(?!\.[A-Za-z0-9])"


def boundary_pattern(forms):
    """Match whole path words: "docs/plan" must not match "docs/plan-archive" or "mydocs/plan"."""
    parts = []
    for f in forms:
        h = HEAD if f[0].isalnum() or f[0] in "_-" else ""
        t = TAIL if f[-1].isalnum() or f[-1] in "_-" else ""
        parts.append(h + re.escape(f) + t)
    return re.compile("|".join(parts)) if parts else re.compile(r"(?!x)x")


def token_before(s, i):
    """The path-like run of characters ending at index i (exclusive)."""
    j = i
    while j > 0 and (s[j - 1].isalnum() or s[j - 1] in "_.-/\\"):
        j -= 1
    return s[j:i]


def ref_matcher(root, target, kind=None, basename=False):
    """Returns (forms, is_ref) where is_ref(text) says whether text references target.

    Loud over silent: a relative form that follows a separator ("X/docs/...") is a hit, except when
    X/docs is itself an existing, different path under the root (site/docs is its own folder). So
    $ROOT/docs, ${workspaceFolder}/docs, <rootDir>/docs, ./docs, parent-relative links and repository
    web URLs all count; a nested folder that merely shares the name does not."""
    rel_forms, abs_forms = spellings(root, target, kind)
    name = os.path.basename(os.path.normpath(target))
    # A bare top-level folder name ("docs") is prose unless it follows a separator ("<rootDir>/docs",
    # "$ROOT/docs"); --basename makes every bare mention count.
    bare_needs_sep = name not in rel_forms and not basename
    if rel_forms and name not in rel_forms and (basename or "/" not in rel_forms[0].rstrip("/\\")):
        rel_forms = rel_forms + [name]
    rel_pat, abs_pat = boundary_pattern(rel_forms), boundary_pattern(abs_forms)
    root_abs = os.path.abspath(root)
    target_abs = os.path.normcase(os.path.abspath(os.path.join(root, target)))

    def _is_other(p):
        return p.startswith(root_abs) and os.path.normcase(p) != target_abs and os.path.lexists(p)

    def is_ref(text):
        if abs_forms and abs_pat.search(text):
            return True
        for m in rel_pat.finditer(text):
            i = m.start()
            if i == 0 or text[i - 1] not in "/\\":
                if bare_needs_sep and m.group(0) == name:
                    continue  # prose, e.g. "read the docs"
                return True
            token = token_before(text, i - 1).replace("\\", "/").strip("/")
            if not token or token.rsplit("/", 1)[-1] in (".", ".."):
                return True
            path = m.group(0).strip("\"'`").rstrip("/\\")
            # try every suffix of the token ("ROOT/site", then "site"): "$ROOT/site/docs" and
            # a GitHub "tree/main/site/docs" URL are the nested site/docs, not root docs
            segs = token.split("/")
            if any(_is_other(os.path.abspath(os.path.join(root_abs, *segs[k:], path)))
                   for k in range(len(segs)) if segs[k] not in ("", ".", "..")):
                continue  # a different path that exists here, e.g. site/docs for root docs
            return True
        return False

    return rel_forms + abs_forms, is_ref


def find_refs(root, target, excludes, basename=False, allow=None, skip_ignore_files=False, kind=None):
    """allow: a path whose spellings are masked first, so "archive/old" does not count as a hit for "old".
    Hits inside the target itself are included and marked, since they need repointing too."""
    forms, is_ref = ref_matcher(root, target, kind, basename)
    masks = []
    if allow:
        masks = sorted(sum(spellings(root, allow, "file"), []) + sum(spellings(root, allow, "dir"), []),
                       key=len, reverse=True)
    self_rel = posix(os.path.relpath(os.path.abspath(os.path.join(root, target)), os.path.abspath(root)))
    hits = []
    for rel, text in text_files(root, excludes):
        name = rel.rsplit("/", 1)[-1]
        if skip_ignore_files and name.startswith(".") and name.endswith("ignore"):
            continue
        inside = rel == self_rel or rel.startswith(self_rel + "/")
        for n, line in enumerate(text.splitlines(), 1):
            probe = line
            for m in masks:
                probe = probe.replace(m, " ")
            if is_ref(probe):
                hits.append((rel + (" [inside target]" if inside else ""), n, line.strip()[:200]))
    return forms, hits


# ---------------------------------------------------------------- hashing

def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_map(path):
    """{relpath: content-sha} for a tree, relative to the tree root. For a single file the key is ".".
    Symlinks are recorded by target, not followed. Empty dirs are not represented."""
    if not os.path.lexists(path):
        raise FileNotFoundError(path)
    if not os.path.isdir(path) or os.path.islink(path):
        return {".": ("link:" + os.readlink(path)) if os.path.islink(path) else file_sha(path)}
    out = {}
    for f in walk_files(path, skip=set()):
        rel = posix(os.path.relpath(f, path))
        out[rel] = ("link:" + os.readlink(f)) if os.path.islink(f) else file_sha(f)
    return out


def tree_hash(path):
    """sha256 over sorted 'relpath<TAB>content-sha' lines. Names inside the tree count; the name of the
    tree root itself does not, so a folder and its renamed copy hash the same."""
    fmap = file_map(path)
    h = hashlib.sha256()
    for rel in sorted(fmap):
        h.update(f"{rel}\t{fmap[rel]}\n".encode("utf-8"))
    size = sum(os.path.getsize(os.path.join(path, r)) for r, d in fmap.items()
               if not d.startswith("link:")) if os.path.isdir(path) else os.path.getsize(path)
    return h.hexdigest(), len(fmap), size


def compare_maps(want, path, skip=()):
    """Every file in `want` must exist under path with the same content, except those in skip (which
    must only exist). Extra files under path are ignored. Returns (missing, changed) lists of relpaths."""
    got = file_map(path) if os.path.lexists(path) else {}
    missing = [r for r in want if r not in got]
    changed = [r for r in want if r in got and r not in skip and got[r] != want[r]]
    return missing, changed


# ---------------------------------------------------------------- inventory

def list_entries(root, depth, excludes):
    """Entries down to depth levels; parents are listed as well as their children."""
    out = []

    def rec(rel, level):
        full = os.path.join(root, rel) if rel else root
        for name in sorted(os.listdir(full)):
            r = f"{rel}/{name}" if rel else name
            if name in SKIP_DIRS or excluded(r, excludes):
                continue
            out.append(r)
            p = os.path.join(root, r)
            if level + 1 < depth and os.path.isdir(p) and not os.path.islink(p):
                rec(r, level + 1)

    rec("", 0)
    return out


def cmd_inventory(a):
    root = a.root
    entries = list_entries(root, a.depth, a.exclude)
    counts = git_state_counts(root, a.depth) if in_git(root) else None
    rows = []
    for rel in entries:
        full = os.path.join(root, rel)
        size = files = 0
        newest = 0.0
        for f in walk_files(full, skip=SKIP_DIRS):
            try:
                st = os.lstat(f)
            except OSError:
                continue
            size += st.st_size
            files += 1
            newest = max(newest, st.st_mtime)
        if files == 0:
            try:
                newest = os.lstat(full).st_mtime
            except OSError:
                pass
        last_commit = ""
        if counts is not None and a.last_commit:
            last_commit = (git(root, "log", "-1", "--format=%cs", "--", rel) or "").strip()
        rows.append({
            "path": rel + ("/" if os.path.isdir(full) and not os.path.islink(full) else ""),
            "kind": "link" if os.path.islink(full) else ("dir" if os.path.isdir(full) else "file"),
            "bytes": size, "files": files,
            "newest_mtime": datetime.date.fromtimestamp(newest).isoformat() if newest else "",
            "git": git_label(rel, counts),
            "last_commit": last_commit,
            "refs": None,
        })

    if a.refs:
        needles = {r["path"].rstrip("/"): set() for r in rows}
        # the same matcher as `refs`; files inside an entry do not count as referencing it
        patterns = {n: ref_matcher(root, n)[1] for n in needles}
        for srel, text in text_files(root, a.exclude):
            for needle, found in needles.items():
                if srel == needle or srel.startswith(needle + "/"):
                    continue  # a folder mentioning itself is not a reference
                if patterns[needle](text):
                    found.add(srel)
        for r in rows:
            r["refs"] = len(needles[r["path"].rstrip("/")])

    rows.sort(key=lambda r: (-r["bytes"], r["path"])) if a.sort == "size" else rows.sort(key=lambda r: r["path"])
    cols = ["path", "kind", "bytes", "files", "newest_mtime", "git", "last_commit", "refs"]
    if a.format == "json":
        print(json.dumps(rows, indent=2))
    elif a.format == "md":
        print("| " + " | ".join(cols) + " |")
        print("|" + "---|" * len(cols))
        for r in rows:
            print("| " + " | ".join("" if r[c] is None else str(r[c]) for c in cols) + " |")
    else:
        print("\t".join(cols))
        for r in rows:
            print("\t".join("" if r[c] is None else str(r[c]) for c in cols))
    total = sum(r["bytes"] for r in rows if "/" not in r["path"].rstrip("/"))
    print(f"# {len(rows)} entries, {total} bytes, git={'yes' if counts is not None else 'no'}, "
          f"refs={'scanned' if a.refs else 'not scanned (use --refs)'}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------- refs / hash

def cmd_refs(a):
    forms, hits = find_refs(a.root, a.target, a.exclude, a.basename, kind=a.kind)
    print("# searched for: " + " | ".join(forms), file=sys.stderr)
    for rel, n, line in hits:
        print(f"{rel}:{n}: {line}")
    print(f"# {len(hits)} referencing line(s) in {len({h[0] for h in hits})} file(s)", file=sys.stderr)
    return 0


def cmd_hash(a):
    status = 0
    for p in a.paths:
        try:
            digest, files, size = tree_hash(p)
            print(f"{digest}\t{files} files\t{size} bytes\t{p}")
        except FileNotFoundError:
            print(f"MISSING\t{p}", file=sys.stderr)
            status = 1
    return status


# ---------------------------------------------------------------- manifest

OPS = ("move", "archive", "delete", "keep")


def is_url(s):
    return "://" in s


def summarize(paths, limit=5):
    shown = ", ".join(paths[:limit])
    return shown + (f" (+{len(paths) - limit} more)" if len(paths) > limit else "")


def cmd_log(a):
    src = os.path.join(a.root, a.src)
    row = {"ts": now(), "step": a.step, "op": a.op, "src": a.src, "dst": a.dst,
           "status": "done" if a.done else "intent"}
    if a.op in ("move", "archive") and not a.dst:
        print("refused: move/archive needs --dst", file=sys.stderr)
        return 2
    if a.edited and not a.done:
        print("refused: --edited belongs on the --done row (declare files you repointed after the move)",
              file=sys.stderr)
        return 2
    if a.absent:
        if os.path.lexists(src):
            print(f"refused: --absent but {a.src} exists", file=sys.stderr)
            return 1
        row["status"] = "absent"
    elif not a.done:
        # write-ahead: record what the source IS before touching it. A missing source is loud, never skipped.
        if not os.path.lexists(src):
            print(f"refused: source {a.src} does not exist. If it was already gone, record that with --absent.",
                  file=sys.stderr)
            return 1
        if a.op == "delete" and not (a.covered_by or a.approved_by):
            print("refused: a delete needs --covered-by (where the content survives) or --approved-by (who "
                  "approved discarding it)", file=sys.stderr)
            return 1
        fmap = file_map(src)
        row["tree_sha"], row["files"], row["bytes"] = tree_hash(src)
        row["file_shas"] = fmap
        row["kind"] = path_kind(a.root, a.src)
        if a.op == "delete" and a.covered_by and not is_url(a.covered_by):
            cover = os.path.join(a.root, a.covered_by)
            if not os.path.lexists(cover):
                print(f"refused: cover {a.covered_by} does not exist", file=sys.stderr)
                return 1
            missing, changed = compare_maps(fmap, cover)
            if missing or changed:
                print(f"refused: {a.covered_by} does not cover {a.src}: "
                      f"{len(missing)} file(s) missing, {len(changed)} with different content "
                      f"({summarize(missing + changed)}). Same name is not same content. If discarding the "
                      f"difference is intended, get approval and use --approved-by instead of --covered-by.",
                      file=sys.stderr)
                return 1
    if a.done and a.edited:
        edited = [posix(os.path.normpath(e)) for e in a.edited]
        gone = [e for e in edited if not os.path.lexists(os.path.join(a.root, e))]
        if gone:
            print(f"refused: --edited file(s) do not exist: {summarize(gone)}", file=sys.stderr)
            return 1
        row["edited"] = edited
    if a.covered_by:
        row["covered_by"] = a.covered_by
    if a.approved_by:
        row["approved_by"] = a.approved_by
    if a.note:
        row["note"] = a.note
    os.makedirs(os.path.dirname(os.path.abspath(a.manifest)), exist_ok=True)
    with open(a.manifest, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row) + "\n")
    shown = {k: v for k, v in row.items() if k != "file_shas"}
    print(json.dumps(shown))
    return 0


def cmd_check(a):
    rows = []
    with open(a.manifest, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if line.strip():
                rows.append((n, json.loads(line)))
    root = a.root
    fails, notes = [], []
    by_key = {}
    edited = set()
    later = []  # (line, src) of completed moves/deletes: a file may legitimately leave an earlier destination
    moves = []  # (line, src, dst) of completed moves, to follow a path through later steps
    for n, r in rows:
        by_key.setdefault((r.get("step"), r["op"], r["src"]), {})[r["status"]] = (n, r)
        edited.update(r.get("edited", []))
        if r["status"] == "done" and r["op"] in ("move", "archive", "delete"):
            later.append((n, posix(os.path.normpath(r["src"]))))
            if r["op"] != "delete":
                moves.append((n, posix(os.path.normpath(r["src"])), posix(os.path.normpath(r["dst"]))))

    def left_later(path, after):
        return any(ln > after and (path == s or path.startswith(s + "/")) for ln, s in later)

    def follow(path, after):
        """Where path lives now, following logged moves made after line `after`."""
        path = posix(os.path.normpath(path))
        for ln, s, d in sorted(moves):
            if ln > after and (path == s or path.startswith(s + "/")):
                path = d + path[len(s):]
        return path

    touched = []
    for key, states in by_key.items():
        if "intent" in states and "done" not in states:
            n = states["intent"][0]
            fails.append(f"line {n}: {key[1]} {key[2]} has an intent row but no done row (interrupted step?)")
        if "done" not in states:
            continue
        n, done = states["done"]
        intent = states.get("intent", (None, {}))[1]
        op, src, dst = done["op"], done["src"], done.get("dst")
        src_p = os.path.join(root, src)
        want = intent.get("file_shas")
        # kind decides how the old path is searched for; the source is gone by now, so it comes from the row
        kind = intent.get("kind") or (("file" if "." in want else "dir") if want else "file")
        if op in ("move", "archive"):
            dst_rel = follow(dst, n)
            dst_p = os.path.join(root, dst_rel)
            if os.path.lexists(src_p):
                fails.append(f"line {n}: {op} {src}: source still exists")
            if not os.path.lexists(dst_p):
                fails.append(f"line {n}: {op} {src}: destination {dst_rel} missing")
            elif want is not None and not a.no_hash:
                full = {r: dst_rel if r == "." else f"{dst_rel}/{r}" for r in want}
                skip = {r for r in want if full[r] in edited}
                missing, changed = compare_maps(want, dst_p, skip)
                missing = [r for r in missing if not left_later(full[r], n)]
                changed = [r for r in changed if not left_later(full[r], n)]
                if missing:
                    fails.append(f"line {n}: {op} {src} -> {dst}: {len(missing)} source file(s) missing at the "
                                 f"destination: {summarize([full[r] for r in missing])}")
                if changed:
                    fails.append(f"line {n}: {op} {src} -> {dst}: {len(changed)} file(s) changed but not "
                                 f"declared with --edited: {summarize([full[r] for r in changed])}")
            touched.append((src, dst, False, kind))
        elif op == "delete":
            if os.path.lexists(src_p):
                fails.append(f"line {n}: delete {src}: still exists")
            cov = intent.get("covered_by") or done.get("covered_by")
            if cov and not is_url(cov):
                cov_now = follow(cov, n)  # a cover moved by a later logged step is followed
                cov_p = os.path.join(root, cov_now)
                if cov_now != posix(os.path.normpath(cov)):
                    cov = f"{cov} (now {cov_now})"
                if not os.path.lexists(cov_p):
                    fails.append(f"line {n}: delete {src}: cover {cov} does not exist")
                elif want is not None and not a.no_hash:
                    missing, changed = compare_maps(want, cov_p)
                    if missing or changed:
                        fails.append(f"line {n}: delete {src}: cover {cov} does not hold the deleted content "
                                     f"({len(missing)} missing, {len(changed)} different: "
                                     f"{summarize(missing + changed)})")
            if not (cov or intent.get("approved_by") or done.get("approved_by")):
                fails.append(f"line {n}: delete {src}: no covered_by and no approved_by")
            touched.append((src, None, True, kind))
        elif op == "keep":
            if not os.path.lexists(src_p):
                fails.append(f"line {n}: keep {src}: missing")
    for key, states in by_key.items():
        if "absent" in states:
            notes.append(f"line {states['absent'][0]}: {key[2]} recorded as already absent")

    stale = 0
    if not a.skip_refs:
        excludes = list(a.exclude)
        try:
            mdir = posix(os.path.relpath(os.path.dirname(os.path.abspath(a.manifest)), os.path.abspath(root)))
            if not mdir.startswith(os.pardir) and mdir != ".":
                excludes.append(mdir + "/*")
        except ValueError:
            pass
        for src, dst, is_delete, kind in touched:
            # a deleted, ignored directory keeps its ignore line on purpose; ignore files are skipped for deletes
            _, hits = find_refs(root, src, excludes, allow=dst, skip_ignore_files=is_delete, kind=kind)
            for rel, ln, line in hits:
                stale += 1
                fails.append(f"stale reference to {src}: {rel}:{ln}: {line}")

    for s in notes:
        print("NOTE " + s)
    for s in fails:
        print("FAIL " + s)
    done_rows = sum(1 for s in by_key.values() if "done" in s)
    print(f"# {len(rows)} rows, {done_rows} completed operations, {len(fails)} failure(s), "
          f"{stale} stale reference line(s)" + (" [refs not scanned]" if a.skip_refs else ""))
    return 1 if fails else 0


# ---------------------------------------------------------------- cli

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("inventory", help="one row per entry under ROOT")
    s.add_argument("root")
    s.add_argument("--depth", type=int, default=1)
    s.add_argument("--format", choices=("tsv", "md", "json"), default="tsv")
    s.add_argument("--sort", choices=("size", "path"), default="size")
    s.add_argument("--refs", action="store_true", help="count files that mention each entry's path (slower)")
    s.add_argument("--last-commit", action="store_true", help="git date of the last commit touching each entry")
    s.add_argument("--exclude", action="append", default=[], help="glob to skip (repeatable)")
    s.set_defaults(fn=cmd_inventory)

    s = sub.add_parser("refs", help="find text files that mention TARGET")
    s.add_argument("target")
    s.add_argument("--root", default=".")
    s.add_argument("--basename", action="store_true", help="also match the bare file/folder name (noisy)")
    s.add_argument("--kind", choices=("file", "dir"),
                   help="what TARGET is/was; read from disk if it exists, else assumed file (use dir for a "
                        "folder that is already gone)")
    s.add_argument("--exclude", action="append", default=[])
    s.set_defaults(fn=cmd_refs)

    s = sub.add_parser("hash", help="content hash of files or trees")
    s.add_argument("paths", nargs="+")
    s.set_defaults(fn=cmd_hash)

    s = sub.add_parser("log", help="append a write-ahead manifest row")
    s.add_argument("--manifest", required=True)
    s.add_argument("--root", default=".")
    s.add_argument("--step", type=int, required=True)
    s.add_argument("--op", choices=OPS, required=True)
    s.add_argument("--src", required=True, help="path relative to --root")
    s.add_argument("--dst")
    s.add_argument("--covered-by", help="where deleted content still lives (path or URL)")
    s.add_argument("--approved-by", help="who approved this destructive step")
    s.add_argument("--note")
    s.add_argument("--edited", action="append", default=[],
                   help="with --done: a file (root-relative) inside the destination that you changed on "
                        "purpose, e.g. to repoint a reference (repeatable)")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--done", action="store_true", help="record completion of an earlier intent row")
    g.add_argument("--absent", action="store_true", help="record that the source was already gone")
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("check", help="verify a manifest against the disk")
    s.add_argument("manifest")
    s.add_argument("--root", default=".")
    s.add_argument("--exclude", action="append", default=[],
                   help="glob of files allowed to keep old paths (history, changelogs); "
                        ".cleanup/ and this skill's own folder are always skipped")
    s.add_argument("--no-hash", action="store_true",
                   help="skip content comparison (weakens the completeness proof; say so in the report)")
    s.add_argument("--skip-refs", action="store_true")
    s.set_defaults(fn=cmd_check)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
