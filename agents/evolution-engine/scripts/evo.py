#!/usr/bin/env python3
"""evo.py - the evidence ledger for the evolution-engine skill.

Python 3 standard library only. Creates and maintains an append-only ledger of
evolution proposals for an agent setup (prompts, rule files, hooks, skills,
loop configs) and enforces the cycle's hard gates deterministically:

  * a proposal is refused (and logged as `incomplete`, so refusals leave a
    trace) unless it cites known parameters, backs every evidence bullet with a
    number and a checkable source, states a numeric baseline, pre-registers
    measurable gate criteria, has a rollback plan and changes one variable;
  * the proposal's full text is hashed at propose time - enact is refused if the
    file changed since then, so the human approves exactly what gets enacted;
  * nothing is enacted without a named human approver;
  * only one change per target is measured at a time (no confounded windows);
  * at enactment the Baseline, Gate Criteria and min_n TEXT is frozen into the
    ledger; `improved` / `no_change` are refused if the file no longer matches
    (no moving the goalposts) or fewer than min_n runs were measured;
  * `reverted` (regression, roll back) is always allowed, at any N, even if the
    proposal file was edited or lost - rolling back is never blocked.

Layout it creates (default: ./.evolution, override with --dir or EVOLUTION_DIR):

  .evolution/ledger.jsonl        append-only event log (the source of truth)
  .evolution/proposals/          one markdown proposal per change
  .evolution/reviews/            periodic evolution reviews

Commands: init, new, check, propose, reject, enact, measure, verdict, rollback,
status, show. Run `python evo.py <command> -h` for details.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

VERDICTS = ("improved", "no_change", "reverted")
PARAMETERS = ("cost", "gate_friction", "override_rate", "handoff_quality", "test_integrity",
              "faked_completeness", "output_quality", "delegation", "context_pressure",
              "check_precision")
CUSTOM_RE = re.compile(r"^custom:([a-z0-9][a-z0-9_-]*)$")
MIN_N_FLOOR = 3
REQUIRED_FIELDS = ("id", "target", "title", "variable", "parameters_cited", "min_n")
REQUIRED_SECTIONS = ("Evidence", "Baseline", "Hypothesis", "Gate Criteria", "Change", "Rollback")
ID_RE = re.compile(r"^EVO-(\d{3,})$")
# a checkable source names something a stranger can look up: a number (run id,
# PR, commit sha, date), a path, a #reference or a file name like hooks.log
CHECKABLE_SOURCE_RE = re.compile(r"\d|/|#|\w\.\w")

TEMPLATE = """---
id: {id}
target: {target}
title: {title}
date: {date}
variable: <!-- the ONE thing this change alters, e.g. "retry limit in the review hook" -->
parameters_cited: <!-- comma-separated keys from references/parameters.md, or custom:<name> -->
min_n: 3
---

# {id}: {title}

## Evidence
<!-- One bullet per data point. Every bullet has a number and ends with a
checkable source (file path, run id, commit, transcript, CI job, PR #). -->
- [parameter] observation with numbers - source: <where you read it>

## Baseline
<!-- The current value of each cited parameter, with N and the window it covers. -->

## Hypothesis
<!-- Mechanism: what you change, why it should move the parameter, and what you
checked to confirm the diagnosis before proposing. -->

## Gate Criteria
<!-- Pre-registered. Frozen at enactment. One line each, with a threshold number. -->
- improved:
- no_change:
- reverted:

## Change
<!-- Exact files and the exact edit. One variable only. -->

## Rollback
<!-- How to undo it: a commit to revert, or the original text to restore. -->
"""


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def today():
    return datetime.date.today().isoformat()


def fail(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def target_key(target):
    """`CLAUDE.md`, `claude-md` and `Claude MD` are the same target."""
    return re.sub(r"[^a-z0-9]", "", str(target).lower())


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- ledger io

class Ledger:
    def __init__(self, directory):
        self.dir = Path(directory)
        self.path = self.dir / "ledger.jsonl"
        self.root = self.dir.resolve().parent

    def require(self):
        if not self.path.exists():
            fail(f"no ledger at {self.path.as_posix()} - run `evo.py init` first")

    def events(self):
        self.require()
        out = []
        with self.path.open(encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    fail(f"ledger line {n} is not valid JSON - the ledger is append-only, fix by hand")
        return out

    def append(self, event):
        self.require()
        event = {"ts": now(), **event}
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def rel(self, p):
        try:
            return Path(os.path.relpath(Path(p).resolve(), self.root)).as_posix()
        except ValueError:  # different drive on Windows
            return Path(p).resolve().as_posix()

    def abs(self, rel):
        p = Path(rel)
        return p if p.is_absolute() else self.root / p

    def states(self):
        """Fold the event log into one record per proposal id (later events win)."""
        recs = {}
        for e in self.events():
            pid = e.get("id")
            if not pid:
                continue
            r = recs.setdefault(pid, {"id": pid, "state": None, "measurements": [], "events": []})
            r["events"].append(e)
            kind = e.get("event")
            if kind in ("proposed", "incomplete"):
                r.update({k: e[k] for k in ("target", "title", "variable", "path", "parameters_cited",
                                            "min_n", "content_hash") if k in e})
                r["state"] = kind
            elif kind == "rejected":
                r["state"] = "rejected"
            elif kind == "enacted":
                r["state"] = "pending"
                r["frozen"] = e.get("frozen", {})
                r["min_n"] = r["frozen"].get("min_n", r.get("min_n"))
            elif kind == "measurement":
                r["measurements"].append(e)
            elif kind == "verdict":
                r["state"] = e.get("verdict")
                r["rollback_required"] = e.get("rollback_required", False)
                r["rolled_back"] = bool(e.get("rollback_ref"))
            elif kind == "rolled_back":
                r["rolled_back"] = True
        return recs


# ------------------------------------------------------------ proposal parse

def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def parse_proposal(path):
    text = Path(path).read_text(encoding="utf-8")
    fields, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, flags=re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fields[k.strip()] = strip_comments(v).strip()
        body = m.group(2)
    sections, current = {}, None
    for line in body.splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            current = h.group(1)
            sections[current] = []
        elif current:
            sections[current].append(line)
    sections = {k: "\n".join(v) for k, v in sections.items()}
    return fields, sections


def content_hash(path):
    return sha(Path(path).read_text(encoding="utf-8").replace("\r\n", "\n"))


def frozen_criteria(fields, sections):
    """The part of a proposal that is fixed at enactment."""
    frozen = {
        "min_n": fields.get("min_n", ""),
        "baseline": strip_comments(sections.get("Baseline", "")).strip(),
        "gate_criteria": strip_comments(sections.get("Gate Criteria", "")).strip(),
    }
    frozen["hash"] = sha("\n".join([str(frozen["min_n"]), frozen["baseline"], frozen["gate_criteria"]]))
    return frozen


def cited_parameters(fields):
    return [p.strip() for p in fields.get("parameters_cited", "").split(",") if p.strip()]


def check_proposal(path):
    """Return (fields, sections, errors, warnings)."""
    errors, warnings = [], []
    if not Path(path).exists():
        return {}, {}, [f"file not found: {path}"], []
    fields, sections = parse_proposal(path)

    for f in REQUIRED_FIELDS:
        if not fields.get(f):
            errors.append(f"frontmatter field `{f}` is missing or empty")
    if fields.get("id") and not ID_RE.match(fields["id"]):
        errors.append(f"id `{fields['id']}` must look like EVO-001")

    ev = strip_comments(sections.get("Evidence", ""))
    cited = cited_parameters(fields)
    if not cited:
        errors.append("parameters_cited is empty - a proposal must cite at least one "
                      "parameter with supporting data (no evidence, no evolution)")
    for p in cited:
        c = CUSTOM_RE.match(p)
        if c:
            if c.group(1) not in ev:
                errors.append(f"`{p}` is a custom parameter - define `{c.group(1)}` in the Evidence "
                              "section (what it counts, unit of a run, where the number comes from)")
        elif p not in PARAMETERS:
            errors.append(f"unknown parameter `{p}` - use one of: {', '.join(PARAMETERS)}, "
                          "or custom:<name> defined in Evidence")

    try:
        min_n = int(fields.get("min_n", ""))
        if min_n < MIN_N_FLOOR:
            errors.append(f"min_n={min_n} is below the floor of {MIN_N_FLOOR}")
    except ValueError:
        errors.append("min_n must be an integer")

    variable = fields.get("variable", "")
    if re.search(r"[,;]", variable):
        errors.append("`variable` lists more than one thing - one variable per proposal, split it")
    elif re.search(r"\band\b", variable):
        warnings.append("`variable` contains 'and' - make sure this is ONE change, not two")

    for s in REQUIRED_SECTIONS:
        if s not in sections:
            errors.append(f"section `## {s}` is missing")
        elif not strip_comments(sections[s]).strip():
            errors.append(f"section `## {s}` is empty")

    bullets = [ln.strip() for ln in ev.splitlines() if re.match(r"^\s*[-*]\s+\S", ln)]
    if not bullets:
        errors.append("Evidence has no bullet points - one bullet per data point")
    for b in bullets:
        m = re.search(r"source\s*:\s*(.*)$", b, flags=re.I)
        observation = b[:m.start()] if m else b
        if not m or not m.group(1).strip():
            errors.append(f"evidence bullet cites no source: {b[:70]}")
        elif m.group(1).strip().startswith("<"):
            errors.append(f"evidence bullet still has the template placeholder: {b[:70]}")
        elif not CHECKABLE_SOURCE_RE.search(m.group(1)):
            errors.append(f"source is not checkable (name a file, run id, commit, PR # or date): {b[:70]}")
        if not re.search(r"\d", observation):
            errors.append(f"evidence bullet has no number - data, not opinion: {b[:70]}")

    if "Baseline" in sections and not re.search(r"\d", strip_comments(sections["Baseline"])):
        errors.append("Baseline contains no numbers - state the current value, N and window")

    gc = strip_comments(sections.get("Gate Criteria", ""))
    for v in VERDICTS:
        m = re.search(rf"^[ \t]*[-*][ \t]*{v}[ \t]*:[ \t]*(.*)$", gc, flags=re.M)
        if not m or not m.group(1).strip():
            errors.append(f"Gate Criteria needs a filled `- {v}:` line")
        elif not re.search(r"\d", m.group(1)):
            errors.append(f"Gate Criteria `{v}:` has no threshold number - make it measurable")
    return fields, sections, errors, warnings


def report(errors, warnings):
    for w in warnings:
        print(f"  warn: {w}")
    for e in errors:
        print(f"  FAIL: {e}")


# ---------------------------------------------------------------- commands

def cmd_init(args, L):
    L.dir.mkdir(parents=True, exist_ok=True)
    (L.dir / "proposals").mkdir(exist_ok=True)
    (L.dir / "reviews").mkdir(exist_ok=True)
    if not L.path.exists():
        L.path.write_text("", encoding="utf-8")
        print(f"created {L.path.as_posix()}")
    else:
        print(f"ledger already exists: {L.path.as_posix()}")


def next_id(L):
    nums = [0]
    for pid in L.states():
        m = ID_RE.match(pid)
        if m:
            nums.append(int(m.group(1)))
    for p in (L.dir / "proposals").glob("EVO-*.md"):
        m = re.match(r"EVO-(\d+)", p.name)
        if m:
            nums.append(int(m.group(1)))
    return f"EVO-{max(nums) + 1:03d}"


def cmd_new(args, L):
    L.require()
    pid = next_id(L)
    slug = re.sub(r"[^a-z0-9]+", "-", (args.slug or args.title).lower()).strip("-")[:40]
    path = L.dir / "proposals" / f"{pid}-{slug}.md"
    path.write_text(TEMPLATE.format(id=pid, target=args.target, title=args.title, date=today()),
                    encoding="utf-8", newline="\n")
    print(path.as_posix())


def cmd_check(args, L):
    _, _, errors, warnings = check_proposal(args.proposal)
    report(errors, warnings)
    print("PASS" if not errors else f"REFUSED ({len(errors)} problem(s))")
    sys.exit(1 if errors else 0)


def cmd_propose(args, L):
    fields, _, errors, warnings = check_proposal(args.proposal)
    pid = fields.get("id") or "EVO-unknown"
    recs = L.states()
    prior = recs.get(pid, {})
    if prior.get("state") not in (None, "incomplete", "proposed"):
        fail(f"{pid} is already `{prior['state']}` - its proposal is closed; write a new proposal "
             f"(`evo.py new`) instead of reusing the id")
    report(errors, warnings)
    base = {
        "id": pid, "path": L.rel(args.proposal),
        "target": fields.get("target", ""), "title": fields.get("title", ""),
        "variable": fields.get("variable", ""), "parameters_cited": cited_parameters(fields),
    }
    if errors:
        if prior.get("state") == "proposed":
            print(f"REFUSED - the edited file no longer passes. {pid} stays `proposed` with its "
                  "previous text; enact will refuse until a passing version is proposed.")
        else:
            L.append({**base, "event": "incomplete", "errors": errors})
            print(f"REFUSED - {pid} logged as `incomplete`. Fix the proposal and propose again.")
        sys.exit(1)
    chash = content_hash(args.proposal)
    if prior.get("state") == "proposed" and prior.get("content_hash") == chash:
        print(f"{pid} is already proposed with exactly this text - nothing logged.")
        return
    L.append({**base, "event": "proposed", "min_n": int(fields["min_n"]), "content_hash": chash})
    verb = "re-proposed (supersedes the earlier text)" if prior.get("state") == "proposed" else "logged as `proposed`"
    print(f"{pid} {verb}. Next: present it to a human for approval.")


def get(L, pid, *states):
    recs = L.states()
    if pid not in recs:
        fail(f"{pid} is not in the ledger")
    r = recs[pid]
    if states and r["state"] not in states:
        fail(f"{pid} is `{r['state']}`; this command needs {' or '.join(states)}")
    return r, recs


def cmd_reject(args, L):
    get(L, args.id, "proposed")
    L.append({"id": args.id, "event": "rejected", "by": args.by, "reason": args.reason})
    print(f"{args.id} rejected (never enacted).")


def cmd_enact(args, L):
    r, recs = get(L, args.id, "proposed")
    clash = [o["id"] for o in recs.values()
             if o["state"] == "pending" and target_key(o.get("target")) == target_key(r.get("target"))]
    if clash:
        fail(f"target `{r.get('target')}` already has a change under measurement ({', '.join(clash)}). "
             "One variable at a time: reach a verdict on it first (`reverted` is always available).")
    path = L.abs(r["path"])
    if not path.exists():
        fail(f"proposal file {r['path']} is missing - restore it or propose again")
    if content_hash(path) != r.get("content_hash"):
        fail("the proposal file changed since it was proposed. Run `evo.py propose` on it again "
             "and get the human's approval for the current text before enacting.")
    fields, sections, errors, _ = check_proposal(path)
    if errors:
        report(errors, [])
        fail("the proposal no longer passes the check - fix it and propose it again")
    frozen = frozen_criteria(fields, sections)
    frozen["min_n"] = int(frozen["min_n"])
    L.append({"id": args.id, "event": "enacted", "approved_by": args.approved_by,
              "ref": args.ref or "", "frozen": frozen})
    print(f"{args.id} enacted -> `pending`. Baseline, gate criteria and min_n are frozen in the ledger. "
          f"Measure {frozen['min_n']}+ runs before a verdict.")


def parse_value(v):
    try:
        return float(v)
    except ValueError:
        return v


def cmd_measure(args, L):
    r, _ = get(L, args.id, "pending")
    metrics = {}
    for kv in args.metric:
        if "=" not in kv:
            fail(f"--metric expects name=value, got `{kv}`")
        k, v = (s.strip() for s in kv.split("=", 1))
        metrics[k] = parse_value(v)
    if any(m.get("run") == args.run for m in r["measurements"]):
        fail(f"run `{args.run}` is already recorded for {args.id} - each run counts once")
    frozen = r.get("frozen", {})
    known = " ".join([frozen.get("baseline", ""), frozen.get("gate_criteria", ""),
                      " ".join(r.get("parameters_cited", []))]).lower()
    for k in metrics:
        parts = [p for p in re.split(r"[_\-\s]+", k.lower()) if len(p) >= 3] or [k.lower()]
        if not any(p in known for p in parts):
            print(f"  warn: metric `{k}` is not named in the baseline, gate criteria or cited "
                  "parameters - measure what the criteria judge")
    L.append({"id": args.id, "event": "measurement", "run": args.run,
              "metrics": metrics, "note": args.note or ""})
    print(f"{args.id}: {len(r['measurements']) + 1}/{r.get('min_n')} runs measured.")


def print_frozen(frozen):
    print("  frozen at enactment (from the ledger):", file=sys.stderr)
    print(f"    min_n: {frozen.get('min_n')}", file=sys.stderr)
    print("    ## Baseline\n" + "\n".join("    " + ln for ln in frozen.get("baseline", "").splitlines()),
          file=sys.stderr)
    print("    ## Gate Criteria\n" + "\n".join("    " + ln for ln in frozen.get("gate_criteria", "").splitlines()),
          file=sys.stderr)


def cmd_verdict(args, L):
    r, _ = get(L, args.id, "pending")
    frozen = r.get("frozen", {})
    n, min_n = len(r["measurements"]), int(r.get("min_n") or MIN_N_FLOOR)
    path = L.abs(r["path"])
    if path.exists():
        fields, sections = parse_proposal(path)
        criteria_changed = frozen_criteria(fields, sections)["hash"] != frozen.get("hash")
    else:
        criteria_changed = True
    if args.keep and args.verdict != "no_change":
        fail("--keep only applies to no_change")
    if args.verdict != "reverted":
        if criteria_changed:
            print_frozen(frozen)
            fail(f"the proposal file {'is missing' if not path.exists() else 'no longer matches the frozen criteria'}"
                 " - the goalposts moved. Restore the Baseline / Gate Criteria / min_n shown above, or record "
                 "`reverted` (always allowed) and re-propose.")
        if n < min_n:
            fail(f"only {n}/{min_n} runs measured - `{args.verdict}` needs the pre-registered N. "
                 "(`reverted` is allowed at any N if you see a regression.)")
    rollback_required = args.verdict == "reverted" or (args.verdict == "no_change" and not args.keep)
    L.append({"id": args.id, "event": "verdict", "verdict": args.verdict, "n": n,
              "rollback_required": rollback_required, "rollback_ref": args.rollback_ref or "",
              "criteria_changed": criteria_changed, "reason": args.reason})
    if criteria_changed:
        print("  note: recorded with criteria_changed=true (proposal file edited or missing)")
    if not rollback_required:
        action = "keep the change"
    elif args.rollback_ref:
        action = f"rolled back ({args.rollback_ref})"
    else:
        action = (f"ROLL THE CHANGE BACK now (proposal's Rollback section), then record it with "
                  f"`evo.py rollback {args.id} --ref <commit or description>`")
    print(f"{args.id} -> {args.verdict} at N={n}. Action: {action}.")


def cmd_rollback(args, L):
    r, _ = get(L, args.id, "no_change", "reverted")
    if not r.get("rollback_required"):
        fail(f"{args.id} was kept (no rollback required)")
    if r.get("rolled_back"):
        fail(f"{args.id} is already recorded as rolled back")
    L.append({"id": args.id, "event": "rolled_back", "ref": args.ref})
    print(f"{args.id} rollback recorded ({args.ref}).")


def cmd_status(args, L):
    recs = [r for r in L.states().values()
            if not args.target or target_key(r.get("target")) == target_key(args.target)]
    if args.json:
        print(json.dumps([{k: v for k, v in r.items() if k != "events"} for r in recs], indent=2))
        return
    if not recs:
        print("ledger is empty" if not args.target else f"no proposals for target `{args.target}`")
        return
    print(f"{'id':<9} {'state':<11} {'N':>6}  {'target':<24} title")
    for r in sorted(recs, key=lambda x: x["id"]):
        n = f"{len(r['measurements'])}/{r.get('min_n', '-')}"
        due = "  [ROLLBACK DUE]" if r.get("rollback_required") and not r.get("rolled_back") else ""
        print(f"{r['id']:<9} {r['state'] or '?':<11} {n:>6}  {str(r.get('target', ''))[:24]:<24} "
              f"{r.get('title', '')}{due}")


def cmd_show(args, L):
    r, _ = get(L, args.id)
    for e in r["events"]:
        print(json.dumps(e, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", default=os.environ.get("EVOLUTION_DIR", ".evolution"),
                    help="ledger directory (default: ./.evolution or $EVOLUTION_DIR)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("init", help="create the ledger directory")
    p = sp.add_parser("new", help="scaffold a proposal file with the next id")
    p.add_argument("--target", required=True, help="what is changed; name it by repo path, e.g. CLAUDE.md")
    p.add_argument("--title", required=True)
    p.add_argument("--slug")
    p = sp.add_parser("check", help="validate a proposal without logging it")
    p.add_argument("proposal")
    p = sp.add_parser("propose", help="validate and log a proposal; re-run after edits while still proposed")
    p.add_argument("proposal")
    p = sp.add_parser("reject", help="record a human rejection")
    p.add_argument("id")
    p.add_argument("--by", required=True)
    p.add_argument("--reason", required=True)
    p = sp.add_parser("enact", help="record human approval + enactment; freezes the gate criteria")
    p.add_argument("id")
    p.add_argument("--approved-by", required=True)
    p.add_argument("--ref", help="commit sha or description of the applied change")
    p = sp.add_parser("measure", help="record one measured run")
    p.add_argument("id")
    p.add_argument("--run", required=True, help="run/session identifier (counted once)")
    p.add_argument("--metric", action="append", default=[], required=True,
                   help="name=value, repeatable")
    p.add_argument("--note")
    p = sp.add_parser("verdict", help="close a pending evolution")
    p.add_argument("id")
    p.add_argument("verdict", choices=VERDICTS)
    p.add_argument("--reason", required=True)
    p.add_argument("--keep", action="store_true",
                   help="no_change only: keep the change anyway (reason must justify it)")
    p.add_argument("--rollback-ref", help="if the rollback is already done: its commit or description")
    p = sp.add_parser("rollback", help="record that a required rollback was carried out")
    p.add_argument("id")
    p.add_argument("--ref", required=True, help="revert commit sha or description")
    p = sp.add_parser("status", help="one line per proposal")
    p.add_argument("--target")
    p.add_argument("--json", action="store_true")
    p = sp.add_parser("show", help="print every ledger event for one id")
    p.add_argument("id")

    args = ap.parse_args(argv)
    L = Ledger(args.dir)
    {"init": cmd_init, "new": cmd_new, "check": cmd_check, "propose": cmd_propose,
     "reject": cmd_reject, "enact": cmd_enact, "measure": cmd_measure, "verdict": cmd_verdict,
     "rollback": cmd_rollback, "status": cmd_status, "show": cmd_show}[args.cmd](args, L)


if __name__ == "__main__":
    main()
