#!/usr/bin/env python3
"""Deterministic checker for a harness registry (harness-creator skill, schema v1).

Validates harnesses/registry.yaml, every definition it references, and the intake transcripts it
lists, against references/schema.md. No LLM, no network.

Usage (from the repo root):
  python .claude/skills/harness-creator/scripts/harness_check.py [--root harnesses]
  python .claude/skills/harness-creator/scripts/harness_check.py --selftest

Exit codes: 0 = no errors (warnings may be printed), 1 = errors, 2 = usage/environment problem.
Requires PyYAML (pip install pyyaml); without it, use the manual checklist in references/schema.md.
"""
import argparse
import copy
import datetime
import os
import re
import sys
import tempfile

try:
    import yaml
except ImportError:  # optional dependency: fail loudly, never silently pass
    yaml = None

STATUSES = {"unproven", "active", "retired"}
RUNBOOK_KEYS = ["how_to_run", "stage_and_scale", "live_env_access", "qa_method", "roadmap", "guardrails"]
NODE_TYPES = {"ai", "deterministic", "human_gate", "verifier"}
TERMINAL_STATES = {"success", "blocked", "approval-required", "exhausted", "no-progress", "clean-no-op"}
SF_KINDS = {"verifier-rejects-bad", "verifier-approves-good", "deterministic-fails-broken",
            "postcheck-fails-missing", "other"}
ID_RX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLACEHOLDER_RX = re.compile(r"^\s*(unknown|none|standard|the usual|as usual|same as before|-+|\.\.\.)\s*[.!]?\s*$",
                            re.I)
# A deferral is an uppercase TBD/TBA/TODO word, any-case tbd/tba/todo standing alone or followed by a
# separator, or a leading "?". "TBD - ask ops" is refused; "Todo app backend API" is a real answer.
DEFERRAL_RX = re.compile(r"^\s*(?:(?-i:TBD|TBA|TODO)\b|(?:tbd|tba|todo)\s*(?:$|[:\-(,;.!?])|\?)", re.I)
BRACES_RX = re.compile(r"\{[^{}\s][^{}]*\}")
NA_RX = re.compile(r"^\s*n/?a\b[\s:(\-]*(.*)$", re.I | re.S)
MIN_ANSWER = 8  # shortest text accepted as an answer or an N/A reason


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s: %s" % (where, msg))


def is_date(v):
    return isinstance(v, datetime.date) or (isinstance(v, str) and bool(DATE_RX.match(v)))


def placeholder_problem(s):
    """Shared by answers and N/A reasons: a placeholder, a deferral, or leftover template braces."""
    if PLACEHOLDER_RX.match(s) or DEFERRAL_RX.match(s):
        return "placeholder %r (answer it, or write 'N/A (reason)')" % s.strip()
    if BRACES_RX.search(s):
        return "unfilled template braces in %r (use <name> for runtime parameters)" % s.strip()[:60]
    return None


def text_problem(v):
    """Return why a free-text value is unacceptable, or None if it is fine."""
    if not isinstance(v, str) or not v.strip():
        return "missing or empty"
    m = NA_RX.match(v)
    if m:
        reason = m.group(1).strip().rstrip(")").strip()
        if len(reason) < MIN_ANSWER or not re.search(r"[A-Za-z]", reason):
            return "N/A without a reason (write 'N/A (reason)')"
        p = placeholder_problem(reason)
        return "N/A reason is a %s" % p if p else None
    p = placeholder_problem(v)
    if p:
        return p
    if len(v.strip()) < MIN_ANSWER:
        return "too short to be an answer (%r; minimum %d characters)" % (v.strip(), MIN_ANSWER)
    return None


def load(path, rep, where):
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except yaml.YAMLError as e:
        rep.err(where, "YAML parse error: %s" % str(e).splitlines()[0])
    except OSError as e:
        rep.err(where, "cannot read: %s" % e)
    return None


def check_definition(root, entry, rep):
    rel = entry["definition"]
    where = rel
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        rep.err(entry["id"], "definition %s does not exist" % rel)
        return None
    d = load(path, rep, where)
    if not isinstance(d, dict):
        if d is not None:
            rep.err(where, "top level must be a mapping")
        return None
    if d.get("id") != entry.get("id"):
        rep.err(where, "id %r does not match registry id %r" % (d.get("id"), entry.get("id")))
    if d.get("version") != entry.get("version"):
        rep.err(where, "version %r does not match registry version %r" % (d.get("version"), entry.get("version")))

    terminals = d.get("terminal_states")
    if not isinstance(terminals, dict) or "success" not in terminals:
        rep.err(where, "terminal_states must be a mapping that includes 'success'")
        terminals = terminals if isinstance(terminals, dict) else {}
    for t in terminals:
        if t not in TERMINAL_STATES:
            rep.err(where, "terminal state %r not in %s" % (t, sorted(TERMINAL_STATES)))

    nodes = d.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        rep.err(where, "nodes must be a non-empty list")
        nodes = []
    ids, types = set(), []
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            rep.err(where, "node #%d is not a mapping" % i)
            continue
        nid = n.get("id") or "#%d" % i
        w = "%s node %s" % (where, nid)
        if nid in ids:
            rep.err(w, "duplicate node id")
        ids.add(nid)
        t = n.get("type")
        types.append(t)
        if t not in NODE_TYPES:
            rep.err(w, "type %r not in %s" % (t, sorted(NODE_TYPES)))
        if t == "deterministic":
            if not str(n.get("command") or "").strip():
                rep.err(w, "deterministic node needs a command")
            if not isinstance(n.get("on_failure"), dict) or not str(n["on_failure"].get("prompt") or "").strip():
                rep.err(w, "deterministic node needs on_failure.prompt (norm + remediation)")
        if t == "verifier":
            for key, want in (("fresh_session", True), ("read_only", True), ("unskippable", True)):
                if n.get(key) is not want:
                    rep.err(w, "verifier must set %s: true" % key)
            if str(n.get("exemptions")).strip().lower() != "none":
                rep.err(w, "verifier must set exemptions: none")
        if t == "human_gate":
            if n.get("terminal_on_reject") is not True:
                rep.err(w, "human gate must set terminal_on_reject: true")
            if not isinstance(n.get("terminal_state"), str) or n["terminal_state"] not in terminals:
                rep.err(w, "terminal_state %r is not declared in terminal_states" % n.get("terminal_state"))
    for n in nodes:
        if isinstance(n, dict):
            for dep in n.get("depends_on") or []:
                if dep not in ids:
                    rep.err("%s node %s" % (where, n.get("id")), "depends_on unknown node %r" % dep)
    if nodes and isinstance(nodes[-1], dict) and nodes[-1].get("type") != "deterministic":
        rep.err(where, "last node must be a deterministic postcheck (found %r)" % nodes[-1].get("type"))
    writers = [n for n in nodes if isinstance(n, dict) and n.get("type") == "ai" and n.get("read_only") is not True]
    if writers and "verifier" not in types:
        rep.warn(where, "AI node(s) %s write but there is no verifier node (self-verification risk)"
                 % [n.get("id") for n in writers])

    for i, b in enumerate(d.get("capability_blocks") or []):
        if not isinstance(b, dict) or not b.get("block") or not isinstance(b.get("adopted"), bool) \
                or not str(b.get("reason") or "").strip():
            rep.err(where, "capability_blocks #%d needs block, adopted (true/false) and reason" % i)

    sfs = d.get("seeded_failures")
    if not isinstance(sfs, list):
        rep.err(where, "seeded_failures must be a list")
        sfs = []
    if len(sfs) < 3:
        rep.err(where, "at least 3 seeded failures required (found %d)" % len(sfs))
    sf_ids, kinds = set(), set()
    for i, sf in enumerate(sfs):
        if not isinstance(sf, dict):
            rep.err(where, "seeded failure #%d is not a mapping" % i)
            continue
        sid = sf.get("id") or "#%d" % i
        w = "%s %s" % (where, sid)
        if sid in sf_ids:
            rep.err(w, "duplicate seeded failure id")
        sf_ids.add(sid)
        if sf.get("kind") not in SF_KINDS:
            rep.err(w, "kind %r not in %s" % (sf.get("kind"), sorted(SF_KINDS)))
        kinds.add(sf.get("kind"))
        if not str(sf.get("test") or "").strip():
            rep.err(w, "test description missing")
        if not isinstance(sf.get("proven"), bool):
            rep.err(w, "proven must be true or false")
        elif sf["proven"] and not str(sf.get("proof") or "").strip():
            rep.err(w, "proven: true without a proof")
    required = {"postcheck-fails-missing"}
    if "verifier" in types:
        required.add("verifier-rejects-bad")
    if "deterministic" in types[:-1]:
        required.add("deterministic-fails-broken")
    for k in sorted(required - kinds):
        rep.err(where, "missing required seeded failure kind %r" % k)
    return d


def check(root):
    rep = Report()
    reg_path = os.path.join(root, "registry.yaml")
    if not os.path.isfile(reg_path):
        rep.err("registry.yaml", "not found under %s" % root)
        return rep
    reg = load(reg_path, rep, "registry.yaml")
    if reg is None and rep.errors:
        return rep
    if not isinstance(reg, dict) or not isinstance(reg.get("harnesses"), list):
        rep.err("registry.yaml", "top level must be a mapping with a 'harnesses' list")
        return rep

    seen, referenced = set(), set()
    entries = [e for e in reg["harnesses"] if isinstance(e, dict)]
    if len(entries) != len(reg["harnesses"]):
        rep.err("registry.yaml", "every item in harnesses must be a mapping")
    all_ids = {e.get("id") for e in entries}
    for e in entries:
        hid = e.get("id")
        w = str(hid)
        if not isinstance(hid, str) or not ID_RX.match(hid):
            rep.err(w, "id must be kebab-case")
        if hid in seen:
            rep.err(w, "duplicate id")
        seen.add(hid)
        for key in ("name", "project"):
            if not str(e.get(key) or "").strip():
                rep.err(w, "%s is required" % key)
        status = e.get("status")
        if status not in STATUSES:
            rep.err(w, "status %r not in %s" % (status, sorted(STATUSES)))
        if not isinstance(e.get("version"), int) or isinstance(e.get("version"), bool) or e["version"] < 1:
            rep.err(w, "version must be an integer >= 1")
        if not is_date(e.get("created_at")):
            rep.err(w, "created_at must be YYYY-MM-DD")
        if "updated_at" in e and not is_date(e.get("updated_at")):
            rep.err(w, "updated_at must be YYYY-MM-DD")
        p = text_problem(e.get("description"))
        if p:
            rep.err(w, "description: %s" % p)

        rb = e.get("runbook")
        if not isinstance(rb, dict):
            rep.err(w, "runbook (six facts) is required - hard gate")
        else:
            for k in RUNBOOK_KEYS:
                p = text_problem(rb.get(k))
                if p:
                    rep.err(w, "runbook.%s: %s" % (k, p))

        caps = e.get("capabilities")
        if not isinstance(caps, list) or not caps:
            rep.err(w, "capabilities must be a non-empty list")
        else:
            for c in caps:
                p = text_problem(c)
                if p:
                    rep.err(w, "capability: %s" % p)

        intake = e.get("intake")
        if not isinstance(intake, list) or not intake:
            rep.err(w, "intake must list at least the birth certificate")
        else:
            for t in intake:
                if not isinstance(t, str) or not os.path.isfile(os.path.join(root, t)):
                    rep.err(w, "intake transcript %r does not exist" % t)

        for dep in e.get("depends_on") or []:
            if dep not in all_ids:
                rep.warn(w, "depends_on %r is not in the registry" % dep)

        defn = None
        if e.get("definition"):
            referenced.add(os.path.normpath(e["definition"]))
            defn = check_definition(root, e, rep)

        if status == "active":
            if not e.get("definition"):
                rep.err(w, "active requires a definition with proven seeded failures")
            if e.get("blocking_facts"):
                rep.err(w, "active while blocking_facts are listed")
            if isinstance(defn, dict):
                open_sf = [s.get("id") for s in defn.get("seeded_failures") or []
                           if isinstance(s, dict) and not (s.get("proven") is True and str(s.get("proof") or "").strip())]
                if open_sf:
                    rep.err(w, "active but seeded failures not proven: %s" % open_sf)
        if status == "retired":
            r = e.get("retired")
            if not isinstance(r, dict) or not is_date(r.get("at")) or not str(r.get("reason") or "").strip():
                rep.err(w, "retired requires retired.at (YYYY-MM-DD) and retired.reason")

    for f in sorted(os.listdir(root)):
        if f.endswith((".yaml", ".yml")) and f != "registry.yaml" and os.path.normpath(f) not in referenced:
            rep.warn(f, "definition file not referenced by any registry entry (orphan)")
    return rep


# ---------------------------------------------------------------- selftest (seeded failures)

GOOD_ENTRY = {
    "id": "demo", "name": "Demo", "project": "demo-repo", "status": "active", "version": 1,
    "created_at": "2026-01-01", "description": "Demo pipeline used by the checker selftest.",
    "definition": "demo.yaml",
    "runbook": {
        "how_to_run": "Manual: run the demo command with a target file as input.",
        "stage_and_scale": "Local only, on demand, one run per target.",
        "live_env_access": "N/A (pure local file transform; touches no live system)",
        "qa_method": "Verifier verdict plus postcheck; receipts in harnesses/receipts.md",
        "roadmap": "Standalone; nothing depends on it yet.",
        "guardrails": "Never writes outside the target file; human gate before ship.",
    },
    "capabilities": ["Transforms one file"],
    "intake": ["intake/demo-create-2026-01-01.md"],
}
GOOD_DEF = {
    "id": "demo", "version": 1,
    "nodes": [
        {"id": "implement", "type": "ai", "read_only": False, "fresh_session": True},
        {"id": "lint", "type": "deterministic", "command": "lint .", "on_failure": {"prompt": "norm + fix"}},
        {"id": "verify", "type": "verifier", "fresh_session": True, "read_only": True,
         "unskippable": True, "exemptions": "none"},
        {"id": "gate", "type": "human_gate", "terminal_on_reject": True, "terminal_state": "approval-required"},
        {"id": "postcheck", "type": "deterministic", "command": "postcheck", "on_failure": {"prompt": "norm + fix"},
         "depends_on": ["gate"]},
    ],
    "terminal_states": {"success": "done", "approval-required": "rejected at gate"},
    "seeded_failures": [
        {"id": "sf-1", "kind": "verifier-rejects-bad", "test": "t", "proven": True, "proof": "p"},
        {"id": "sf-2", "kind": "deterministic-fails-broken", "test": "t", "proven": True, "proof": "p"},
        {"id": "sf-3", "kind": "postcheck-fails-missing", "test": "t", "proven": True, "proof": "p"},
    ],
}


def _set(obj, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        obj = obj[int(k)] if isinstance(obj, list) else obj[k]
    last = keys[-1]
    if value is _DEL:
        if isinstance(obj, list):
            del obj[int(last)]
        else:
            obj.pop(last, None)
    elif isinstance(obj, list):
        obj[int(last)] = value
    else:
        obj[last] = value


_DEL = object()

# (description, target "entry"|"def", dotted path, value, expected error substring)
MUTATIONS = [
    ("runbook fact missing", "entry", "runbook.guardrails", _DEL, "runbook.guardrails"),
    ("runbook placeholder", "entry", "runbook.roadmap", "TBD", "placeholder"),
    ("bare N/A", "entry", "runbook.live_env_access", "N/A", "N/A without a reason"),
    ("template braces left", "entry", "runbook.how_to_run", "{R1 answer}", "template braces"),
    ("no capabilities", "entry", "capabilities", [], "capabilities"),
    ("missing birth certificate", "entry", "intake", ["intake/nope.md"], "does not exist"),
    ("bad status", "entry", "status", "done", "status"),
    ("active with unproven seeded failure", "def", "seeded_failures.0.proven", False, "not proven"),
    ("proven without proof", "def", "seeded_failures.1.proof", "", "without a proof"),
    ("skippable verifier", "def", "nodes.2.unskippable", False, "unskippable"),
    ("verifier exemption", "def", "nodes.2.exemptions", "trivial diffs", "exemptions"),
    ("deterministic without remediation", "def", "nodes.1.on_failure", _DEL, "on_failure.prompt"),
    ("gate without terminal state", "def", "nodes.3.terminal_state", "blocked", "not declared"),
    ("last node not a postcheck", "def", "nodes.4", {"id": "ship", "type": "ai"}, "last node"),
    ("too few seeded failures", "def", "seeded_failures.2", _DEL, "at least 3"),
    ("version mismatch", "def", "version", 2, "version"),
    ("active with blocking facts", "entry", "blocking_facts", ["no data source"], "blocking_facts"),
    ("one-character answer", "entry", "runbook.qa_method", "x", "too short"),
    ("'standard' as an answer", "entry", "runbook.stage_and_scale", "standard", "placeholder"),
    ("'the usual' as an answer", "entry", "runbook.guardrails", "the usual", "placeholder"),
    ("'as usual' as an answer", "entry", "runbook.roadmap", "As usual.", "placeholder"),
    ("deferral with a tail", "entry", "runbook.live_env_access", "TBD - ask ops", "placeholder"),
    ("leading question mark", "entry", "runbook.how_to_run", "? not sure yet", "placeholder"),
    ("N/A whose reason is a deferral", "entry", "runbook.live_env_access", "N/A (TBD later)", "N/A reason"),
    ("one-character capability", "entry", "capabilities", ["x"], "too short"),
]

# Approves-good controls: a gate that rejects everything also passes every seeded failure above.
# (target, dotted path, legitimate value) - each must produce zero errors.
CONTROLS = [
    ("entry", "runbook.live_env_access", "Todo app backend API, read-write via the staging URL"),
    ("entry", "runbook.live_env_access", "Todo items table in Postgres, read-write"),
    ("entry", "runbook.stage_and_scale", "Standard library only; no live systems"),
    ("entry", "runbook.guardrails", "None of its steps touch a live system"),
    ("entry", "runbook.live_env_access", "N/A (pure local transform; no live system)"),
    ("entry", "runbook.qa_method", "Verdict at harnesses/runs/<run-id>/verdict.yaml plus postcheck"),
    ("entry", "capabilities", ["Todo list sync across devices"]),
    ("entry", "description", "Todo app release pipeline: plan, test, verify, merge."),
]


def _write_fixture(root, entry, defn):
    os.makedirs(os.path.join(root, "intake"), exist_ok=True)
    with open(os.path.join(root, "intake", "demo-create-2026-01-01.md"), "w", encoding="utf-8") as fh:
        fh.write("# Birth certificate: demo\n")
    with open(os.path.join(root, "registry.yaml"), "w", encoding="utf-8") as fh:
        yaml.safe_dump({"schema_version": 1, "harnesses": [entry]}, fh, sort_keys=False)
    with open(os.path.join(root, "demo.yaml"), "w", encoding="utf-8") as fh:
        yaml.safe_dump(defn, fh, sort_keys=False)


def selftest():
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "good")
        _write_fixture(base, GOOD_ENTRY, GOOD_DEF)
        rep = check(base)
        ok = not rep.errors
        print("%s  valid fixture passes%s" % ("PASS" if ok else "FAIL", "" if ok else ": %s" % rep.errors))
        failures += not ok
        for i, (desc, target, path, value, expect) in enumerate(MUTATIONS):
            entry, defn = copy.deepcopy(GOOD_ENTRY), copy.deepcopy(GOOD_DEF)
            _set(entry if target == "entry" else defn, path, value)
            root = os.path.join(tmp, "m%02d" % i)
            _write_fixture(root, entry, defn)
            rep = check(root)
            caught = any(expect in e for e in rep.errors)
            print("%s  seeded: %s%s" % ("PASS" if caught else "FAIL", desc,
                                         "" if caught else " (not caught; errors: %s)" % rep.errors))
            failures += not caught
        for i, (target, path, value) in enumerate(CONTROLS):
            entry, defn = copy.deepcopy(GOOD_ENTRY), copy.deepcopy(GOOD_DEF)
            _set(entry if target == "entry" else defn, path, value)
            root = os.path.join(tmp, "c%02d" % i)
            _write_fixture(root, entry, defn)
            rep = check(root)
            ok = not rep.errors
            print("%s  control: %s = %r accepted%s" % ("PASS" if ok else "FAIL", path, value,
                                                     "" if ok else " (errors: %s)" % rep.errors))
            failures += not ok
        root = os.path.join(tmp, "malformed")
        os.makedirs(root)
        with open(os.path.join(root, "registry.yaml"), "w", encoding="utf-8") as fh:
            fh.write("harnesses: [unclosed\n")
        caught = bool(check(root).errors)
        print("%s  seeded: malformed YAML is an error, not a pass" % ("PASS" if caught else "FAIL"))
        failures += not caught
    total = len(MUTATIONS) + len(CONTROLS) + 2
    print("selftest: %d/%d passed" % (total - failures, total))
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description="Validate a harness registry (harness-creator schema v1).")
    ap.add_argument("--root", default="harnesses", help="harness directory (default: harnesses)")
    ap.add_argument("--selftest", action="store_true", help="prove the checker fails on seeded bad input")
    a = ap.parse_args()
    if yaml is None:
        print("harness_check: PyYAML is not installed. Install it (pip install pyyaml) or use the "
              "manual checklist in references/schema.md.")
        return 2
    if a.selftest:
        return selftest()
    if not os.path.isdir(a.root):
        print("harness_check: %s is not a directory" % a.root)
        return 2
    rep = check(a.root)
    for w in rep.warnings:
        print("WARN   " + w)
    for e in rep.errors:
        print("ERROR  " + e)
    print("harness_check: %d error(s), %d warning(s)" % (len(rep.errors), len(rep.warnings)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
