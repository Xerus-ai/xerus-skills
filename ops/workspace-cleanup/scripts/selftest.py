#!/usr/bin/env python3
"""Self-test for cleanup.py: a realistic cleanup in a throwaway folder, with seeded failures.

Every check that is supposed to catch something is first shown to FAIL on bad input, then to pass
once the input is fixed. Run: python selftest.py   (exit 0 = all assertions held)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
RESULTS = []


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def run(root, *args):
    script = os.path.join(root, ".claude", "skills", "workspace-cleanup", "scripts", "cleanup.py")
    r = subprocess.run([sys.executable, script, *args], cwd=root, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def expect(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "\n     " + detail.replace("\n", "\n     ")))


def main():
    root = tempfile.mkdtemp(prefix="cleanup-selftest-")
    try:
        # the skill installed inside the repo it cleans, as a user would have it
        shutil.copytree(SKILL_DIR, os.path.join(root, ".claude", "skills", "workspace-cleanup"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        write(root, "README.md", "Start with docs/guide.md.\nRead the docs before contributing.\n"
                                 "Follow the [setup steps](SETUP.md).\n")
        write(root, "SETUP.md", "# Setup\n")
        write(root, "tools/run.sh", "#!/bin/sh\ncat SETUP.md\n")
        write(root, "tools/README.md", "Back to the [setup](" + ".." + "/SETUP.md).\n")  # parent-relative link
        write(root, "site/docs/index.md", "This site reads site/docs/ only.\n")  # a different, nested docs
        # paths written from a root variable, and a repository web URL: all break when docs/ moves
        write(root, "scripts/ci.sh", '#!/bin/sh\ncat "$ROOT/docs/api.md"\n# spec: https://github.com/acme/widget/blob/main/docs/api.md\n')
        write(root, ".vscode/settings.json", '{\n  "guide": "${workspaceFolder}/docs/guide.md"\n}\n')
        # the NESTED site/docs written from a root variable or a repo URL: not root docs, never flagged
        write(root, "scripts/site.sh", '#!/bin/sh\ncat "$ROOT/site/docs/index.md"\n'
                                       '# https://github.com/acme/widget/tree/main/site/docs\n')
        write(root, "jest.config.js", 'module.exports = { roots: ["<rootDir>/docs"] };\n'
                                      '// cd "$(git rev-parse --show-toplevel)/docs"\n')
        write(root, "docs/guide.md", "# Guide\nSee docs/api.md for the API.\n")
        write(root, "docs/api.md", "# API\n")
        write(root, "tools/check_docs.py", 'import os\nprint("docs check:")\nprint(os.path.exists("docs/api.md"))\n')
        write(root, "assets/logo.svg", "<svg/>\n")
        write(root, "assets-copy/logo.svg", "<svg/>\n")
        write(root, "utils/helpers.py", "def a():\n    return 1\n")
        write(root, "backup/utils/helpers.py", "def a():\n    return 2  # the only copy of this change\n")
        write(root, "notes-2026/ideas.md", "ideas\n")
        write(root, "build/out.txt", "generated\n")
        write(root, ".gitignore", "build/\n")
        M = ".cleanup/2026-01-15/manifest.jsonl"
        write(root, ".cleanup/2026-01-15/plan.md", "| 1 | docs/ | move | handbook/ |\n")

        # refs: path-shaped matches only, own skill folder and .cleanup skipped, hits inside the target shown
        code, out = run(root, "refs", "docs")
        expect("refs finds README and tool", "README.md:1" in out and "tools/check_docs.py:3" in out, out)
        expect("refs shows the reference inside the target", "docs/guide.md [inside target]:2" in out, out)
        expect("refs ignores prose 'the docs' and the string \"docs check:\"",
               "README.md:2" not in out and "check_docs.py:2" not in out, out)
        expect("refs skips the skill's own folder and .cleanup/", ".claude/" not in out and ".cleanup/" not in out, out)
        expect("refs for root docs ignores the unrelated nested site/docs", "site/docs/index.md" not in out, out)
        expect("refs ignores $ROOT/site/docs and tree/main/site/docs (nested folder via a suffix)",
               "scripts/site.sh" not in out, out)
        expect("refs finds root-variable paths and a repo URL ($ROOT/docs, ${workspaceFolder}/docs, blob/main/docs)",
               "scripts/ci.sh:2" in out and "scripts/ci.sh:3" in out and ".vscode/settings.json:2" in out
               and "jest.config.js:1" in out and "jest.config.js:2" in out, out)

        # a root FILE is matched by its plain name (markdown link, unquoted script arg, parent-relative link)
        code, out = run(root, "refs", "SETUP.md")
        expect("refs finds a root file in a markdown link, a script arg and a parent-relative link",
               "README.md:3" in out and "tools/run.sh:2" in out and "tools/README.md:1" in out, out)
        code, inv = run(root, "inventory", ".", "--refs")
        rows = {l.split("\t")[0]: l.split("\t") for l in inv.splitlines() if "\t" in l}
        expect("inventory --refs agrees with refs (same matcher)",
               rows.get("SETUP.md", [""] * 8)[7] == "3" and rows.get("docs/", [""] * 8)[7] == "5", inv)

        # step 1: docs -> handbook, with repointing inside the moved tree
        code, out = run(root, "log", "--manifest", M, "--step", "1", "--op", "move", "--src", "docs", "--dst", "handbook")
        expect("log intent for move", code == 0, out)
        os.rename(os.path.join(root, "docs"), os.path.join(root, "handbook"))
        write(root, "README.md", "Start with handbook/guide.md.\nRead the docs before contributing.\n"
                                 "Follow the [setup steps](SETUP.md).\n")
        write(root, "tools/check_docs.py", 'import os\nprint("docs check:")\nprint(os.path.exists("handbook/api.md"))\n')
        run(root, "log", "--manifest", M, "--step", "1", "--op", "move", "--src", "docs", "--dst", "handbook", "--done")
        code, out = run(root, "check", M)
        expect("SEEDED: stale reference inside the moved tree fails check",
               code == 1 and "stale reference to docs: handbook/guide.md:2" in out, out)
        expect("SEEDED: stale $ROOT/docs and ${workspaceFolder}/docs paths and repo URL fail check",
               "stale reference to docs: scripts/ci.sh:2" in out and "stale reference to docs: scripts/ci.sh:3" in out
               and "stale reference to docs: .vscode/settings.json:2" in out
               and "stale reference to docs: jest.config.js:1" in out and "stale reference to docs: jest.config.js:2" in out, out)
        expect("nested site/docs is still not reported by check",
               "site/docs/index.md" not in out and "scripts/site.sh" not in out, out)
        write(root, "scripts/ci.sh", '#!/bin/sh\ncat "$ROOT/handbook/api.md"\n# spec: https://github.com/acme/widget/blob/main/handbook/api.md\n')
        write(root, ".vscode/settings.json", '{\n  "guide": "${workspaceFolder}/handbook/guide.md"\n}\n')
        # the NESTED site/docs written from a root variable or a repo URL: not root docs, never flagged
        write(root, "scripts/site.sh", '#!/bin/sh\ncat "$ROOT/site/docs/index.md"\n'
                                       '# https://github.com/acme/widget/tree/main/site/docs\n')
        write(root, "jest.config.js", 'module.exports = { roots: ["<rootDir>/handbook"] };\n'
                                      '// cd "$(git rev-parse --show-toplevel)/handbook"\n')
        write(root, "handbook/guide.md", "# Guide\nSee handbook/api.md for the API.\n")
        code, out = run(root, "check", M)
        expect("SEEDED: undeclared edit inside the destination fails check",
               code == 1 and "changed but not declared with --edited: handbook/guide.md" in out, out)
        code, out = run(root, "log", "--manifest", M, "--step", "1", "--op", "move", "--src", "docs",
                        "--dst", "handbook", "--done", "--edited", "handbook/guide.md")
        expect("log --done --edited accepted", code == 0, out)
        code, out = run(root, "check", M)
        expect("move with declared repointing passes check (no --no-hash, no --exclude)", code == 0, out)

        # step 2: a later move INTO the earlier destination must not break step 1
        run(root, "log", "--manifest", M, "--step", "2", "--op", "move", "--src", "notes-2026", "--dst", "handbook/notes")
        os.rename(os.path.join(root, "notes-2026"), os.path.join(root, "handbook", "notes"))
        run(root, "log", "--manifest", M, "--step", "2", "--op", "move", "--src", "notes-2026", "--dst",
            "handbook/notes", "--done")
        code, out = run(root, "check", M)
        expect("nested later move into an earlier destination passes", code == 0, out)

        # step 3: a later move OUT of an earlier destination is recorded, so it is not a loss
        run(root, "log", "--manifest", M, "--step", "3", "--op", "move", "--src", "handbook/api.md", "--dst", "reference/api.md")
        os.makedirs(os.path.join(root, "reference"))
        os.rename(os.path.join(root, "handbook", "api.md"), os.path.join(root, "reference", "api.md"))
        write(root, "handbook/guide.md", "# Guide\nSee reference/api.md for the API.\n")
        write(root, "tools/check_docs.py", 'import os\nprint("docs check:")\nprint(os.path.exists("reference/api.md"))\n')
        write(root, "scripts/ci.sh", '#!/bin/sh\ncat "$ROOT/reference/api.md"\n'
                                     '# spec: https://github.com/acme/widget/blob/main/reference/api.md\n')
        run(root, "log", "--manifest", M, "--step", "3", "--op", "move", "--src", "handbook/api.md", "--dst",
            "reference/api.md", "--done", "--edited", "handbook/guide.md")
        code, out = run(root, "check", M)
        expect("file moved out of an earlier destination by a later logged step passes", code == 0, out)

        # step 3b: a root FILE moves; its plain-name references must be caught after the source is gone
        run(root, "log", "--manifest", M, "--step", "31", "--op", "move", "--src", "SETUP.md", "--dst", "handbook/setup.md")
        os.rename(os.path.join(root, "SETUP.md"), os.path.join(root, "handbook", "setup.md"))
        run(root, "log", "--manifest", M, "--step", "31", "--op", "move", "--src", "SETUP.md", "--dst",
            "handbook/setup.md", "--done")
        code, out = run(root, "check", M)
        expect("SEEDED: moved root file with a broken markdown link / script arg fails check",
               code == 1 and "stale reference to SETUP.md: README.md:3" in out
               and "stale reference to SETUP.md: tools/run.sh:2" in out
               and "stale reference to SETUP.md: tools/README.md:1" in out, out)
        write(root, "README.md", "Start with handbook/guide.md.\nRead the docs before contributing.\n"
                                 "Follow the [setup steps](handbook/setup.md).\n")
        write(root, "tools/run.sh", "#!/bin/sh\ncat handbook/setup.md\n")
        write(root, "tools/README.md", "Back to the [setup](" + ".." + "/handbook/setup.md).\n")
        code, out = run(root, "check", M)
        expect("root file move passes once every reference is repointed", code == 0, out)

        # an unlogged loss from a destination is caught
        os.remove(os.path.join(root, "handbook", "notes", "ideas.md"))
        code, out = run(root, "check", M)
        expect("SEEDED: file missing from a destination fails check",
               code == 1 and "missing at the destination: handbook/notes/ideas.md" in out, out)
        write(root, "handbook/notes/ideas.md", "ideas\n")

        # step 4: byte-identical duplicate delete, covered
        code, out = run(root, "log", "--manifest", M, "--step", "4", "--op", "delete", "--src", "assets-copy",
                        "--covered-by", "assets")
        expect("identical cover accepted", code == 0, out)
        shutil.rmtree(os.path.join(root, "assets-copy"))
        run(root, "log", "--manifest", M, "--step", "4", "--op", "delete", "--src", "assets-copy", "--done")

        # step 4b: the cover itself moves later; check follows the logged move
        run(root, "log", "--manifest", M, "--step", "41", "--op", "move", "--src", "assets", "--dst", "static/assets")
        os.makedirs(os.path.join(root, "static"))
        os.rename(os.path.join(root, "assets"), os.path.join(root, "static", "assets"))
        run(root, "log", "--manifest", M, "--step", "41", "--op", "move", "--src", "assets", "--dst", "static/assets", "--done")
        code, out = run(root, "check", M)
        expect("a cover moved by a later logged step is followed", code == 0, out)

        # step 5: same name, different content is NOT a cover
        code, out = run(root, "log", "--manifest", M, "--step", "5", "--op", "delete", "--src", "backup/utils",
                        "--covered-by", "utils")
        expect("SEEDED: same-name different-content cover refused",
               code == 1 and "does not cover" in out and "--approved-by" in out, out)
        code, out = run(root, "log", "--manifest", M, "--step", "5", "--op", "delete", "--src", "backup/utils")
        expect("SEEDED: delete with no cover and no approval refused", code == 1, out)

        # step 6: approved delete of an ignored, regenerable dir; the ignore line stays
        run(root, "log", "--manifest", M, "--step", "6", "--op", "delete", "--src", "build", "--approved-by", "owner")
        shutil.rmtree(os.path.join(root, "build"))
        run(root, "log", "--manifest", M, "--step", "6", "--op", "delete", "--src", "build", "--done")

        # missing source is loud; --absent records it
        code, out = run(root, "log", "--manifest", M, "--step", "7", "--op", "move", "--src", "fonts", "--dst", "assets/fonts")
        expect("SEEDED: missing source refused", code == 1 and "--absent" in out, out)
        code, out = run(root, "log", "--manifest", M, "--step", "7", "--op", "move", "--src", "fonts",
                        "--dst", "assets/fonts", "--absent")
        expect("--absent recorded", code == 0, out)

        code, out = run(root, "check", M)
        expect("full cleanup passes check with no flags", code == 0 and "0 failure(s)" in out, out)

        # tampering with a cover after the delete is caught
        write(root, "static/assets/logo.svg", "<svg>changed</svg>\n")
        code, out = run(root, "check", M)
        expect("SEEDED: cover changed after delete fails check",
               code == 1 and "does not hold the deleted content" in out, out)
        write(root, "static/assets/logo.svg", "<svg/>\n")

        # an interrupted step is caught
        run(root, "log", "--manifest", M, "--step", "8", "--op", "archive", "--src", "utils", "--dst", "archive/utils")
        code, out = run(root, "check", M)
        expect("SEEDED: intent without done fails check", code == 1 and "no done row" in out, out)

        code, out = run(root, "inventory", ".", "--refs", "--sort", "path")
        rows = {l.split("\t")[0]: l.split("\t") for l in out.splitlines() if "\t" in l}
        expect("inventory runs and does not count .cleanup/ as a referencer",
               code == 0 and rows.get("README.md", [""] * 8)[7] == "0", out)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"# {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
