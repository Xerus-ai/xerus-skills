#!/usr/bin/env python3
"""Validate the files of agent loops scaffolded by the loop-creator skill.

    python check_loops.py [--root loops]   validate every loop under ROOT
    python check_loops.py --selftest       prove the checks FAIL on seeded bad input

Exit codes: 0 = no failures (warnings allowed), 1 = failures, 2 = usage/layout error.
Formats are documented in references/file-formats.md. Python 3 standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import tempfile
from pathlib import Path

TERMINAL_STATES = ("success", "clean no-op", "blocked", "approval-required", "exhausted", "no-progress")
CONTRACT_KEYS = (
    "name", "description", "level", "observes", "writes", "trigger", "intended_cadence",
    "manual_runs_required", "manual_runs_read", "pause_exit_proven",
    "token_budget_per_run", "time_limit_minutes", "crash_pause_threshold", "convergence_threshold",
    "created_at", "graduated_by", "graduated_at", "schedule_approved_by", "schedule_approved_at",
)
INT_KEYS = (
    "manual_runs_required", "manual_runs_read", "token_budget_per_run", "time_limit_minutes",
    "crash_pause_threshold", "convergence_threshold",
)
STATE_KEYS = ("acting_on", "in_progress", "last_run", "last_terminal_state", "consecutive_crashes",
              "report_read_through")
REPORTING_STATES = ("success", "approval-required", "clean no-op")  # runs that produced a real report
RECEIPT_FIELDS = ("result", "evidence", "metric", "tokens_consumed", "wall_clock_minutes")
FINDING_STATUSES = ("open", "watching", "resolved", "noise")
REGISTRY_STATUSES = ("active", "paused", "retired")
EMPTY = ("", "none", "null", "-", "(none)")

RECEIPT_HEAD = re.compile(r"^### Run #(\d+) [-—] (\S+)", re.M)
FIELD = re.compile(r"^- \*\*([^*]+)\*\*:\s*(.*)$", re.M)
KEY_VALUE = re.compile(r"^([a-z_]+):\s*(.*)$")


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []

    def fail(self, where: str, msg: str) -> None:
        self.fails.append(f"FAIL {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warns.append(f"WARN {where}: {msg}")


# ---------------------------------------------------------------- parsing helpers

def clean(raw: str) -> str:
    """Drop a trailing `# comment` and surrounding quotes."""
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip().strip("\"'")


def key_values(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        m = KEY_VALUE.match(line)
        if m:
            out[m.group(1)] = clean(m.group(2))
    return out


def frontmatter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return key_values(lines[1:i])
    return None


def as_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def as_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def leading_number(value: str) -> int | None:
    m = re.search(r"\d[\d,]*", value or "")
    return int(m.group(0).replace(",", "")) if m else None


def base_state(result: str) -> str | None:
    low = result.lower()
    return next((s for s in TERMINAL_STATES if low.startswith(s)), None)


def table_rows(text: str, first_header: str) -> list[list[str]]:
    """Body rows of the first markdown table whose first header cell is `first_header`."""
    rows: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not in_table:
            in_table = cells[0].lower() == first_header.lower()
            continue
        if set(stripped.replace("|", "")) <= set("-: "):
            continue  # separator row
        rows.append(cells)
    return rows


# ---------------------------------------------------------------- checks

def check_registry(root: Path, rep: Report) -> dict[str, dict[str, str]]:
    path = root / "REGISTRY.md"
    if not path.is_file():
        rep.fail("REGISTRY.md", "missing - the loop root needs a registry carrying the pause_all flag")
        return {}
    text = path.read_text(encoding="utf-8")
    if key_values(text.splitlines()).get("pause_all") not in ("true", "false"):
        rep.fail("REGISTRY.md", "pause_all must be present and exactly `true` or `false`")
    rows: dict[str, dict[str, str]] = {}
    for cells in table_rows(text, "Loop"):
        if len(cells) < 6:
            rep.fail("REGISTRY.md", f"row {cells!r} needs 6 columns: "
                     "Loop | Level | Trigger | Intended cadence | Budget/run | Status")
            continue
        name = cells[0].strip("`")
        if name in rows:
            rep.fail("REGISTRY.md", f"duplicate row for {name}")
        if cells[5] not in REGISTRY_STATUSES:
            rep.fail("REGISTRY.md", f"{name}: status must be one of {REGISTRY_STATUSES}")
        rows[name] = {"level": cells[1], "trigger": cells[2].split()[0] if cells[2] else "", "status": cells[5]}
    return rows


def repo_base(root: Path) -> Path:
    """Where `writes:` paths are anchored: nearest ancestor of the loop root holding .git,
    else the folder that contains the loop root."""
    root = root.resolve()
    for folder in (root, *root.parents):
        if (folder / ".git").exists():
            return folder
    return root.parent


def inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def check_contract(root: Path, name: str, row: dict[str, str], rep: Report) -> dict | None:
    where = f"{name}/CONTRACT.md"
    fm = frontmatter((root / name / "CONTRACT.md").read_text(encoding="utf-8"))
    if fm is None:
        rep.fail(where, "no frontmatter block (--- ... ---) at the top")
        return None
    missing = [k for k in CONTRACT_KEYS if k not in fm]
    if missing:
        rep.fail(where, "missing frontmatter keys: " + ", ".join(missing))
        return None
    if fm["name"] != name:
        rep.fail(where, f"name `{fm['name']}` does not match its directory `{name}`")
    ints: dict[str, int] = {}
    for key in INT_KEYS:
        value = as_int(fm[key])
        if value is None or value < 0:
            rep.fail(where, f"{key} must be a non-negative integer, got `{fm[key]}`")
        ints[key] = value or 0
    if ints["manual_runs_required"] < 1:
        rep.fail(where, "manual_runs_required must be at least 1")
    for key in ("token_budget_per_run", "time_limit_minutes", "crash_pause_threshold"):
        if ints[key] < 1:
            rep.fail(where, f"{key} must be at least 1 - an unbounded loop has no hard stop")
    if as_date(fm["created_at"]) is None:
        rep.fail(where, "created_at must be an absolute date (YYYY-MM-DD)")

    level = fm["level"]
    if level not in ("L1", "L2"):
        rep.fail(where, f"level must be L1 or L2, got `{level}`")
    if level == "L1":
        own = (root / name).resolve()
        base = repo_base(root)
        entries = [e.strip() for e in fm["writes"].split(",") if e.strip()]
        if not entries:
            rep.fail(where, "writes is empty - an L1 loop writes its own folder")
        for entry in entries:
            target = (base / entry.replace("\\", "/")).resolve()
            if re.search(r"\s", entry) or not inside(target, own):
                rep.fail(where, f"L1 is report-only: writes entry `{entry}` is not inside "
                         f"`{root.name}/{name}/` (repo-relative paths, comma-separated, no spaces)")
    if level == "L2":
        if fm["graduated_by"] in EMPTY or as_date(fm["graduated_at"]) is None:
            rep.fail(where, "L2 requires graduated_by and graduated_at - graduation is a recorded human decision")

    trigger = fm["trigger"]
    if trigger not in ("manual", "scheduled"):
        rep.fail(where, f"trigger must be manual or scheduled, got `{trigger}`")
    if trigger == "scheduled":
        if ints["manual_runs_read"] < ints["manual_runs_required"]:
            rep.fail(where, f"scheduled before graduation: {ints['manual_runs_read']}/"
                     f"{ints['manual_runs_required']} manual runs with read reports")
        if fm["pause_exit_proven"] != "true":
            rep.fail(where, "scheduled before the pause exit was proven (pause_exit_proven: true)")
        if fm["schedule_approved_by"] in EMPTY or as_date(fm["schedule_approved_at"]) is None:
            rep.fail(where, "scheduled without schedule_approved_by/_at - scheduling is a human decision")

    if row.get("level") != level:
        rep.fail(where, f"level {level} disagrees with registry row ({row.get('level')})")
    if row.get("trigger") != trigger:
        rep.fail(where, f"trigger {trigger} disagrees with registry row ({row.get('trigger')})")
    return {**fm, **ints}


def check_receipts(root: Path, name: str, contract: dict | None, rep: Report, today: dt.date) -> dict:
    where = f"{name}/receipts.md"
    path = root / name / "receipts.md"
    stats = {"runs": 0, "reports": 0, "last_run": "none", "last_state": "none"}
    if not path.is_file():
        rep.fail(where, "missing - a loop without receipts is invisible")
        return stats
    parts = path.read_text(encoding="utf-8").split("## Run Receipts", 1)
    if len(parts) < 2:
        rep.fail(where, "missing the `## Run Receipts` section")
        return stats
    head = key_values(parts[0].splitlines())
    missing = [k for k in STATE_KEYS if k not in head]
    if missing:
        rep.fail(where, "missing header fields: " + ", ".join(missing))
        return stats

    if contract and contract["level"] == "L1" and head["acting_on"].lower() not in EMPTY:
        rep.fail(where, "an L1 loop never acts - acting_on must be `none`")
    crashes = as_int(head["consecutive_crashes"])
    if crashes is None:
        rep.fail(where, "consecutive_crashes must be an integer")
    elif contract and crashes >= contract["crash_pause_threshold"] > 0:
        rep.fail(where, f"{crashes} consecutive crashes reached the threshold - "
                 "a human must review, then reset consecutive_crashes to 0")
    if head["in_progress"].lower() not in EMPTY:
        rep.warn(where, "in_progress is set - a run is live, or the last run died without a receipt")

    body = parts[1]
    heads = list(RECEIPT_HEAD.finditer(body))
    previous: dt.date | None = None
    metrics: list[int | None] = []
    for i, m in enumerate(heads):
        label = f"{where} run #{m.group(1)}"
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        fields = {k.strip().lower(): v.strip() for k, v in FIELD.findall(body[m.start():end])}
        if int(m.group(1)) != i + 1:
            rep.fail(label, f"run numbers must count 1, 2, 3... (expected #{i + 1})")
        date = as_date(m.group(2))
        if date is None:
            rep.fail(label, f"header date `{m.group(2)}` is not an absolute YYYY-MM-DD date")
        else:
            if date > today:
                rep.fail(label, f"dated {date} - in the future; stamp receipts with the real current date")
            if previous and date < previous:
                rep.fail(label, f"dated {date}, earlier than the run before it ({previous})")
            previous = date
        for key in RECEIPT_FIELDS:
            if not fields.get(key):
                rep.fail(label, f"missing `- **{key}**:` line")
        state = base_state(fields.get("result", ""))
        if fields.get("result") and state is None:
            rep.fail(label, f"result `{fields['result']}` is not a terminal state {TERMINAL_STATES}")
        tokens = leading_number(fields.get("tokens_consumed", ""))
        if contract and tokens and tokens > contract["token_budget_per_run"] and state != "exhausted":
            rep.warn(label, f"{tokens} tokens exceeds the {contract['token_budget_per_run']} budget "
                     "but the run did not end `exhausted`")
        metric = fields.get("metric", "")
        metrics.append(leading_number(metric.split("=", 1)[1]) if "=" in metric else None)
        stats.update(runs=i + 1, last_run=m.group(2), last_state=state or "?")
        stats["reports"] += state in REPORTING_STATES

    if heads:
        if head["last_run"] != stats["last_run"]:
            rep.fail(where, f"header last_run `{head['last_run']}` != newest receipt date `{stats['last_run']}`")
        if base_state(head["last_terminal_state"]) != stats["last_state"]:
            rep.fail(where, f"header last_terminal_state `{head['last_terminal_state']}` "
                     f"!= newest receipt result `{stats['last_state']}`")
    elif head["last_run"].lower() not in EMPTY:
        rep.fail(where, "header claims a last_run but there are no receipts")

    read_through = as_int(head["report_read_through"])
    if read_through is None or read_through < 0:
        rep.fail(where, "report_read_through must be a non-negative integer")
    elif read_through > stats["runs"]:
        rep.fail(where, f"report_read_through={read_through} but the newest run is #{stats['runs']}")

    if contract:
        if contract["manual_runs_read"] > stats["reports"]:
            rep.fail(f"{name}/CONTRACT.md", f"manual_runs_read={contract['manual_runs_read']} but only "
                     f"{stats['reports']} runs produced a report ({', '.join(REPORTING_STATES)})")
        k = contract["convergence_threshold"]
        if k and len(metrics) >= k and all(v == 0 for v in metrics[-k:]):
            rep.warn(where, f"metric was 0 for the last {k} runs - propose a slower cadence to the human")
    return stats


def check_findings(root: Path, name: str, rep: Report) -> None:
    path = root / name / "findings.md"
    if not path.is_file():
        return
    where = f"{name}/findings.md"
    seen_ids: set[str] = set()
    for cells in table_rows(path.read_text(encoding="utf-8"), "id"):
        if len(cells) < 6:
            rep.fail(where, f"row {cells!r} needs 6 columns: id | first_seen | last_seen | seen | status | summary")
            continue
        fid, first, last, seen, status = (c.strip("`") for c in cells[:5])
        if fid in seen_ids:
            rep.fail(where, f"duplicate finding `{fid}` - a re-observation bumps seen/last_seen, never adds a row")
        seen_ids.add(fid)
        d1, d2 = as_date(first), as_date(last)
        if d1 is None or d2 is None:
            rep.fail(where, f"`{fid}`: first_seen/last_seen must be YYYY-MM-DD")
        elif d2 < d1:
            rep.fail(where, f"`{fid}`: last_seen is before first_seen")
        if (as_int(seen) or 0) < 1:
            rep.fail(where, f"`{fid}`: seen must be an integer >= 1")
        if status not in FINDING_STATUSES:
            rep.fail(where, f"`{fid}`: status must be one of {FINDING_STATUSES}")


def check(root: Path, today: dt.date | None = None) -> tuple[Report, list[tuple]]:
    rep = Report()
    today = today or dt.date.today()
    rows = check_registry(root, rep)
    dirs = {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))}
    for d in sorted(dirs - set(rows)):
        rep.fail(d, "loop directory has no registry row")
    for n in sorted(set(rows) - dirs):
        rep.fail("REGISTRY.md", f"row `{n}` has no directory")
    summary = []
    for name in sorted(dirs & set(rows)):
        if not (root / name / "CONTRACT.md").is_file():
            rep.fail(name, "no CONTRACT.md - a loop without a contract is a wish")
            continue
        contract = check_contract(root, name, rows[name], rep)
        stats = check_receipts(root, name, contract, rep, today)
        check_findings(root, name, rep)
        read = f"{contract['manual_runs_read']}/{contract['manual_runs_required']}" if contract else "?"
        summary.append((name, rows[name]["level"], rows[name]["trigger"], rows[name]["status"],
                        stats["runs"], read, stats["last_run"], stats["last_state"]))
    return rep, summary


# ---------------------------------------------------------------- self-test

GOOD = {
    "REGISTRY.md": """# Loop Registry

pause_all: false   # global kill switch

| Loop | Level | Trigger | Intended cadence | Budget/run | Status |
|------|-------|---------|------------------|------------|--------|
| demo | L1 | manual | daily | 60000 tokens / 15 min | active |
""",
    "demo/CONTRACT.md": """---
name: demo
description: Seeded self-test loop
level: L1
observes: the repository working tree (read-only)
writes: loops/demo/
trigger: manual
intended_cadence: daily
manual_runs_required: 5
manual_runs_read: 1
pause_exit_proven: false
token_budget_per_run: 60000
time_limit_minutes: 15
crash_pause_threshold: 3
convergence_threshold: 3
created_at: 2026-01-01
graduated_by: none
graduated_at: none
schedule_approved_by: none
schedule_approved_at: none
---

# Demo
""",
    "demo/receipts.md": """# demo - receipts

acting_on: none
in_progress: none
last_run: 2026-01-02
last_terminal_state: success
consecutive_crashes: 0
report_read_through: 1

## Run Receipts

### Run #1 — 2026-01-02
- **Result**: success
- **Evidence**: git log --oneline -5 returned 5 commits
- **Metric**: new_findings = 1
- **tokens_consumed**: ~20000 (estimate)
- **wall_clock_minutes**: 6
""",
    "demo/findings.md": """# demo - findings

| id | first_seen | last_seen | seen | status | summary |
|----|------------|-----------|------|--------|---------|
| stale-lockfile | 2026-01-02 | 2026-01-02 | 1 | open | lockfile older than manifest |
""",
}

PAUSE_RECEIPT = """
### Run #2 — 2026-01-03
- **Result**: blocked (paused)
- **Evidence**: loops/REGISTRY.md has pause_all: true; nothing else read or written
- **Metric**: n/a
- **tokens_consumed**: ~500 (estimate)
- **wall_clock_minutes**: 1
"""

# (label, file, old, new, expected fragment of a FAIL line)
SEEDS = [
    ("pause flag missing", "REGISTRY.md", "pause_all: false", "", "pause_all"),
    ("L1 claims to act", "demo/receipts.md", "acting_on: none", "acting_on: src/app.py", "never acts"),
    ("invented terminal state", "demo/receipts.md", "- **Result**: success", "- **Result**: done", "terminal state"),
    ("scheduled before graduation", "demo/CONTRACT.md", "trigger: manual", "trigger: scheduled", "graduation"),
    ("L2 without human record", "demo/CONTRACT.md", "level: L1", "level: L2", "graduated_by"),
    ("L1 writes outside its folder", "demo/CONTRACT.md", "writes: loops/demo/", "writes: src/", "report-only"),
    ("duplicate finding", "demo/findings.md", "| lockfile older than manifest |",
     "| lockfile older than manifest |\n| stale-lockfile | 2026-01-03 | 2026-01-03 | 1 | open | again |",
     "duplicate finding"),
    ("receipt from the future", "demo/receipts.md", "### Run #1 — 2026-01-02", "### Run #1 — 2999-01-02",
     "future"),
    ("header disagrees with receipt", "demo/receipts.md", "last_terminal_state: success",
     "last_terminal_state: blocked", "last_terminal_state"),
    ("receipt without budget meter", "demo/receipts.md", "- **tokens_consumed**: ~20000 (estimate)\n", "",
     "tokens_consumed"),
    ("crash threshold ignored", "demo/receipts.md", "consecutive_crashes: 0", "consecutive_crashes: 3",
     "consecutive crashes"),
    ("more reads than reports", "demo/CONTRACT.md", "manual_runs_read: 1", "manual_runs_read: 4",
     "only 1 runs produced a report"),
    ("L1 writes: extra space-separated target", "demo/CONTRACT.md", "writes: loops/demo/",
     "writes: loops/demo/ and src/", "report-only"),
    ("L1 writes: same name in another folder", "demo/CONTRACT.md", "writes: loops/demo/",
     "writes: other/loops/demo/", "report-only"),
    ("read-through beyond newest run", "demo/receipts.md", "report_read_through: 1", "report_read_through: 2",
     "report_read_through=2"),
]


def write_fixture(base: Path, files: dict[str, str]) -> Path:
    root = base / "loops"
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def selftest() -> int:
    today = dt.date(2026, 6, 1)
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        rep, _ = check(write_fixture(Path(tmp) / "good", GOOD), today)
        print(f"{'PASS' if not rep.fails else 'FAIL'}  good fixture is accepted")
        for line in rep.fails:
            print("      " + line)
        ok &= not rep.fails
        paused = dict(GOOD, **{
            "REGISTRY.md": GOOD["REGISTRY.md"].replace("pause_all: false", "pause_all: true"),
            "demo/receipts.md": GOOD["demo/receipts.md"].replace(
                "last_terminal_state: success", "last_terminal_state: blocked (paused)").replace(
                "last_run: 2026-01-02", "last_run: 2026-01-03") + PAUSE_RECEIPT,
        })
        rep, _ = check(write_fixture(Path(tmp) / "paused", paused), today)
        print(f"{'PASS' if not rep.fails else 'FAIL'}  a correct pause exit (receipt + header update) is accepted")
        for line in rep.fails:
            print("      " + line)
        ok &= not rep.fails
        for i, (label, rel, old, new, fragment) in enumerate(SEEDS):
            assert old in GOOD[rel], f"seed `{label}` does not apply"
            files = dict(GOOD, **{rel: GOOD[rel].replace(old, new, 1)})
            rep, _ = check(write_fixture(Path(tmp) / f"seed{i}", files), today)
            caught = any(fragment in line for line in rep.fails)
            ok &= caught
            print(f"{'PASS' if caught else 'FAIL'}  seeded: {label}")
        files = dict(GOOD, **{"stray/CONTRACT.md": GOOD["demo/CONTRACT.md"]})
        rep, _ = check(write_fixture(Path(tmp) / "stray", files), today)
        caught = any("no registry row" in line for line in rep.fails)
        ok &= caught
        print(f"{'PASS' if caught else 'FAIL'}  seeded: loop folder missing from registry")
    print("selftest:", "all seeded failures caught" if ok else "CHECKER IS BROKEN")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="loops", help="folder holding REGISTRY.md and one folder per loop")
    ap.add_argument("--selftest", action="store_true", help="run the seeded-failure self-test")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    root = Path(args.root)
    if not root.is_dir():
        print(f"no loop root at {root} - pass --root, or scaffold one first", file=sys.stderr)
        return 2
    rep, summary = check(root)
    if summary:
        print(f"{'loop':<24} {'lvl':<3} {'trigger':<9} {'status':<7} {'runs':>4} {'read':>5}  last run    state")
        for name, lvl, trig, status, runs, read, last, state in summary:
            print(f"{name:<24} {lvl:<3} {trig:<9} {status:<7} {runs:>4} {read:>5}  {last:<10}  {state}")
    for line in rep.warns + rep.fails:
        print(line)
    print(f"{len(rep.fails)} failure(s), {len(rep.warns)} warning(s)")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
