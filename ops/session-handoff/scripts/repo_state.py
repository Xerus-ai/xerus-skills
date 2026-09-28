#!/usr/bin/env python3
"""Print the verified state of one or more git repos as a markdown block for a handoff.

Every row comes from a git command run now, so the handoff's "State you inherit" table
is evidence, not memory. Python 3 stdlib only; needs `git` on PATH.

Usage:
  python repo_state.py                  # the current directory
  python repo_state.py PATH [PATH ...]  # several repos (or plain folders, or bare repos)
  python repo_state.py --fetch PATH     # run `git fetch` first so ahead/behind is current
  python repo_state.py --self-test      # build a throwaway repo and check the parser against it

Reports per repo: current branch, last commit, remotes, pushed or not, staged / modified /
untracked paths, stashes, and every local branch with its upstream, ahead/behind, whether its
tip is on a remote, and whether it is merged into HEAD.

Exit code: 0 when every path was inspected (dirty or not), 2 when a path does not exist,
1 when --self-test fails.
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys
import tempfile

MAX_LISTED = 8  # dirty paths listed per repo before summarising


def git(path, *args):
    """Run git in `path`; return stdout with trailing whitespace removed, or None on failure.

    Only TRAILING whitespace is removed: `git status --porcelain` lines start with a
    meaningful space (" M file" = modified, not staged), so a leading strip corrupts them.
    """
    try:
        out = subprocess.run(
            ["git", "-C", path, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.rstrip() if out.returncode == 0 else None


def on_remote(path, rev):
    """True when `rev` is contained in any remote-tracking branch (as of the last fetch)."""
    return bool(git(path, "for-each-ref", "--contains", rev, "--format=%(refname)", "refs/remotes"))


def branches(path, head_ok):
    """Every local branch: upstream, ahead/behind, on a remote at all, merged into HEAD.

    Parses plumbing / --format output only. Porcelain like `git branch` decorates names
    ("* " current, "+ " checked out in another worktree, ANSI colour under color.ui=always)
    and breaks name matching.
    """
    fmt = "%(refname:short)|%(upstream:short)|%(upstream:track)|%(objectname:short)"
    rows = git(path, "for-each-ref", "--format=" + fmt, "refs/heads") or ""
    merged = set()
    if head_ok:
        merged = set((git(path, "for-each-ref", "--merged", "HEAD", "--format=%(refname:short)",
                          "refs/heads") or "").splitlines())
    out = []
    for row in rows.splitlines():
        name, upstream, track, sha = row.split("|")
        entry = {"name": name, "upstream": upstream, "track": track, "sha": sha, "merged": name in merged}
        if not upstream:
            entry["on_remote"] = on_remote(path, sha)
        out.append(entry)
    return out


def inspect(path, fetch):
    info = {"path": path}
    if not os.path.isdir(path):
        info["error"] = "path does not exist"
        return info
    bare = git(path, "rev-parse", "--is-bare-repository")
    if bare is None:
        info["error"] = "not a git repo (plain folder: record it as such)"
        return info
    info["bare"] = bare == "true"
    if not info["bare"] and git(path, "rev-parse", "--is-inside-work-tree") != "true":
        # e.g. the `.git` directory itself: git answers, but status there is meaningless.
        info["error"] = "inside a git directory, not a working tree: point at the repo root"
        return info
    if fetch:
        info["fetched"] = git(path, "fetch", "--all", "--quiet") is not None

    info["branch"] = git(path, "symbolic-ref", "--short", "-q", "HEAD") or "(detached HEAD)"
    head = git(path, "log", "-1", "--format=%h %s (%ad)", "--date=short")
    info["head"] = head or "(no commits yet)"

    seen = []
    for name in (git(path, "remote") or "").splitlines():
        seen.append(f"{name} -> {git(path, 'remote', 'get-url', '--push', name) or '(no url)'}")
    info["remotes"] = seen
    info["branches"] = branches(path, head is not None)
    if info["bare"]:
        if head is None and info["branches"]:
            info["head"] = "(HEAD's branch has no commits; see branches)"
        return info

    upstream = git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    info["upstream"] = upstream
    if upstream:
        counts = git(path, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        if counts:
            behind, ahead = counts.split()
            info["ahead"], info["behind"] = int(ahead), int(behind)
    elif seen and head:
        # No upstream: is HEAD on ANY remote-tracking branch? If not, it was never pushed.
        info["head_on_remote"] = on_remote(path, "HEAD")

    status = git(path, "status", "--porcelain=v1", "--untracked-files=normal")
    info["status_failed"] = status is None  # unknown is never reported as clean
    staged, modified, untracked = [], [], []
    for line in (status or "").splitlines():
        code, name = line[:2], line[3:]
        if code == "??":
            untracked.append(name)
            continue
        if code[0] not in " ?":
            staged.append(name)
        if code[1] not in " ?":
            modified.append(name)
    info["staged"], info["modified"], info["untracked"] = staged, modified, untracked

    stashes = git(path, "log", "--walk-reflogs", "--format=%H", "refs/stash") or ""
    info["stashes"] = len(stashes.splitlines()) if stashes else 0
    return info


def pushed_cell(info):
    if not info["remotes"]:
        return "no remote (nothing can be pushed)"
    if info.get("upstream"):
        ahead, behind = info.get("ahead", 0), info.get("behind", 0)
        cell = "in sync with " + info["upstream"] if not ahead else f"{ahead} commit(s) NOT pushed to {info['upstream']}"
        if behind:
            cell += f"; {behind} behind"
        return cell + (" (as of last fetch)" if not info.get("fetched") else "")
    if "head_on_remote" in info:
        return "no upstream; HEAD is on a remote branch" if info["head_on_remote"] else "no upstream; HEAD NOT on any remote branch"
    return "no upstream"


def dirty_cell(info):
    if info.get("status_failed"):
        return "git status FAILED: working-tree state unknown (do not record as clean)"
    parts = []
    for label in ("staged", "modified", "untracked"):
        if info[label]:
            parts.append(f"{len(info[label])} {label}")
    if info["stashes"]:
        parts.append(f"{info['stashes']} stash(es)")
    return ", ".join(parts) if parts else "clean"


def branch_line(b, bare=False):
    if bare:  # a bare repo usually IS the remote: upstream / merged-into-HEAD mean nothing here
        return f"- `{b['name']}` at {b['sha']}"
    if b["upstream"]:
        where = f"tracks {b['upstream']} {b['track'] or '[in sync]'}"
    else:
        where = "no upstream; " + ("tip is on a remote branch" if b["on_remote"] else "tip NOT on any remote")
    merged = "merged into HEAD" if b["merged"] else "NOT merged into HEAD"
    return f"- `{b['name']}` at {b['sha']}: {where}; {merged}"


def render(infos):
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z").strip()
    lines = [f"Checked: {now} (repo_state.py)", "",
             "| Repo | Branch | Last commit | Remote(s) | Pushed? | Working tree |",
             "|---|---|---|---|---|---|"]
    for info in infos:
        if "error" in info:
            lines.append(f"| `{info['path']}` | - | - | - | - | {info['error']} |")
            continue
        remotes = "<br>".join(info["remotes"]) or "none"
        if info["bare"]:
            lines.append(f"| `{info['path']}` | {info['branch']} | {info['head']} | {remotes} | - | bare repo (no working tree) |")
            continue
        lines.append(f"| `{info['path']}` | {info['branch']} | {info['head']} | {remotes} | "
                     f"{pushed_cell(info)} | {dirty_cell(info)} |")
    for info in infos:
        if "error" in info:
            continue
        if info["branches"]:
            lines += ["", f"`{info['path']}` local branches ({len(info['branches'])}; track state as of last fetch):"]
            lines += [branch_line(b, info["bare"]) for b in info["branches"]]
        if info["bare"]:
            continue
        listed = [("staged", info["staged"]), ("modified", info["modified"]), ("untracked", info["untracked"])]
        if not any(paths for _, paths in listed):
            continue
        lines += ["", f"`{info['path']}` working tree:"]
        for label, paths in listed:
            for name in paths[:MAX_LISTED]:
                lines.append(f"- {label}: `{name}`")
            if len(paths) > MAX_LISTED:
                lines.append(f"- {label}: ... and {len(paths) - MAX_LISTED} more")
    lines += ["", "Each untracked/modified path above needs a word in the handoff: yours and pending, "
                  "deliberately untracked (why), or not yours (whose). Branches that are not merged and "
                  "not on a remote exist only on this machine."]
    return "\n".join(lines)


def self_test():
    """Seeded cases the parser once got wrong or could get wrong; returns a list of failures."""
    tmp = tempfile.mkdtemp(prefix="repo-state-test-")
    fails = []
    try:
        remote, work = os.path.join(tmp, "origin.git"), os.path.join(tmp, "work")
        ident = ["-c", "user.email=test@example.com", "-c", "user.name=test"]

        def run(cwd, *args):
            subprocess.run(["git", *ident, *args], cwd=cwd, check=True, capture_output=True)

        def write(name, text):
            with open(os.path.join(work, name), "w", encoding="utf-8") as fh:
                fh.write(text)

        run(tmp, "init", "-q", "--bare", remote)
        run(tmp, "init", "-q", work)
        run(work, "checkout", "-q", "-b", "old-feature")
        write("README.md", "one\n")
        run(work, "add", "README.md")
        run(work, "commit", "-q", "-m", "first")
        run(work, "remote", "add", "origin", remote)
        run(work, "push", "-q", "-u", "origin", "old-feature")
        run(work, "checkout", "-q", "-b", "new-feature")
        write("app.txt", "x\n")
        run(work, "add", "app.txt")
        run(work, "commit", "-q", "-m", "second")
        run(work, "checkout", "-q", "-b", "local-only")
        # Unstaged edit to the alphabetically FIRST dirty path: " M README.md" must stay "modified".
        write("README.md", "two\n")
        write("b-staged.txt", "s\n")
        run(work, "add", "b-staged.txt")
        write("c-untracked.txt", "u\n")
        # A merged branch checked out in a second worktree ("+ wt-branch" in `git branch`), and a
        # stash made there (stashes are shared across worktrees).
        wt = os.path.join(tmp, "wt")
        run(work, "branch", "wt-branch", "old-feature")
        run(work, "worktree", "add", "-q", wt, "wt-branch")
        with open(os.path.join(wt, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("stashed\n")
        run(wt, "stash", "-q")
        # Colour forced on: porcelain output would carry ANSI codes; plumbing must not care.
        run(work, "config", "color.ui", "always")
        run(work, "config", "color.branch", "always")

        info = inspect(work, False)
        checks = [
            (info["modified"] == ["README.md"], f"modified == ['README.md'], got {info['modified']}"),
            (info["staged"] == ["b-staged.txt"], f"staged == ['b-staged.txt'], got {info['staged']}"),
            (info["untracked"] == ["c-untracked.txt"], f"untracked == ['c-untracked.txt'], got {info['untracked']}"),
            (info["branch"] == "local-only", f"branch == local-only, got {info['branch']}"),
            (info.get("head_on_remote") is False, "local-only HEAD reported as NOT on a remote"),
        ]
        by_name = {b["name"]: b for b in info["branches"]}
        checks += [
            (set(by_name) == {"old-feature", "new-feature", "local-only", "wt-branch"},
             f"all 4 branches listed, got {sorted(by_name)}"),
            (by_name.get("old-feature", {}).get("upstream") == "origin/old-feature", "old-feature tracks origin/old-feature"),
            (by_name.get("old-feature", {}).get("merged") is True, "old-feature merged into HEAD (color.ui=always)"),
            (by_name.get("local-only", {}).get("merged") is True, "current branch merged into HEAD (color.ui=always)"),
            (by_name.get("wt-branch", {}).get("merged") is True, "worktree branch merged into HEAD"),
            (by_name.get("wt-branch", {}).get("on_remote") is True, "worktree branch tip is on a remote"),
            (by_name.get("new-feature", {}).get("on_remote") is False, "new-feature tip NOT on a remote"),
            (info["remotes"] == [f"origin -> {remote}"], f"remotes == ['origin -> {remote}'], got {info['remotes']}"),
            (info["stashes"] == 1, f"stashes == 1, got {info['stashes']}"),
        ]
        bare = inspect(remote, False)
        checks.append((bare.get("bare") is True and "error" not in bare, "bare repo reported as bare, not plain folder"))
        checks.append(("- `old-feature` at" in render([bare]), "bare repo lists its branches"))
        checks.append(("error" in inspect(tmp, False), "plain folder reported as not a git repo"))
        # Pointed at the (dirty) repo's `.git` directory: must be an error row, never "clean".
        gitdir = render([inspect(os.path.join(work, ".git"), False)])
        checks.append(("not a working tree" in gitdir and "| clean |" not in gitdir,
                       ".git directory reported as not a working tree, not clean"))
        # `git status` itself failing: the row must say unknown, never "clean".
        real_git = globals()["git"]
        globals()["git"] = lambda p, *a: None if a[:1] == ("status",) else real_git(p, *a)
        try:
            failed = render([inspect(work, False)])
        finally:
            globals()["git"] = real_git
        checks.append(("git status FAILED" in failed and "| clean |" not in failed,
                       "failed git status reported as unknown, not clean"))
        fails = [msg for ok, msg in checks if not ok]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--fetch", action="store_true", help="git fetch --all before comparing with upstream")
    ap.add_argument("--self-test", action="store_true", help="check the parser against a throwaway repo")
    args = ap.parse_args()
    if args.self_test:
        fails = self_test()
        for msg in fails:
            print("FAIL: " + msg)
        print("self-test: " + ("FAILED" if fails else "all checks passed"))
        return 1 if fails else 0
    infos = [inspect(p, args.fetch) for p in args.paths]
    print(render(infos))
    return 2 if any(i.get("error") == "path does not exist" for i in infos) else 0


if __name__ == "__main__":
    sys.exit(main())
