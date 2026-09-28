# Writer brief (template)

Copy into `work/batch-NNN/brief.md`, fill the angle brackets, delete what does not apply. Each
writer gets this brief, a copy of `code-verification.md`, plus its own assignment: the clusters it owns and the **exact files** it
may write. No two writers share a file.

---

## Promotion batch <NNN> (<theme>): brief for writer agents (<date>)

Registry root: `<path>`. Archived upstream trees: `archive/objects/<id>/` (read-only; never
edit). Candidates with object file lists: `work/batch-<NNN>/candidates.json`.

### Shape (human-approved <date>, do not re-litigate)

<paste shape.md: the new skills with their fixed file names, the folds into existing skills,
the skips already decided>

### Sources and licence

<per source: origin, licence as detected, snapshot age. Example: "Two MIT upstreams, both
snapshots about eight months old. Assume every version pin is stale.">

Many clusters hold several copies of the same upstream skill. Read ALL of them, keep the
better and more current material, and merge their documented-issue entries.
If any object turns out to have no licence, or an Elastic / Business Source / proprietary /
copyleft licence: copy NOTHING from it and report it. You may write that material fresh from
the vendor's own documentation. Say so in your note.

### What to keep, what to cut

- KEEP: documented-issue catalogs (exact error text -> cause -> fix), limits and quota tables,
  non-obvious gotchas, minimal correct code for the main path.
- CUT: marketing, "when to use this skill" boilerplate, setup repeated from the base skill, long
  template dumps, token-savings claims, changelog noise, anything duplicated in another file.
- **Fold, don't paste.** Rewrite in your own words and in the target's structure. Target
  <120-350> lines per reference file. SKILL.md stays lean. Bulk goes in `references/<topic>.md`
  with one line in SKILL.md saying WHEN to read it.
- If the fold widens a skill's scope, extend its `description` trigger phrases, briefly.

### Currency and correctness (binding)

- For every package you name with a version, check the current version with the package
  manager. **That only checks the number.** It says nothing about whether the API you wrote
  still exists.
- For every code block: follow the attached `code-verification.md`. Type-check against the real, unpacked
  package types in strict mode, fix until clean, and report what you checked.
- For facts you cannot type-check (limits, pricing, beta/GA status, renamed features): check the
  vendor's official docs. If you cannot verify, write "verify against current docs". Do not assert.
- Security-relevant code (token verification, signature checks, access control, secrets
  handling) must be correct against the real library. A plausible "verify" that accepts forged
  tokens is worse than no example.
- Add a one-line `Verified against <sources> on <date>` at the top of each reference file.

### Hard rules

- Write ONLY the files assigned to you. Never touch `archive/`, `decisions.jsonl`,
  `registry-index.json`, the `skill.yaml` of NEW skills (the orchestrator assembles those), or
  any other skill or file.
- No version-control commands that change anything. Reading history is fine.
- Clean up ONLY paths you created, by exact filename. Never `rm` with globs. Never touch shared
  temp directories. Delete any `__pycache__` your runs created inside your folders.
- SKILL.md frontmatter: `name` equals the folder name; `description` <= 1024 chars, says what it
  does and when to use it; double-quote it if it contains `: `. Validate by parsing it with a
  strict YAML parser and checking the length.
- Merge targets (existing skills): append the cluster to `provenance:`, append each archive file
  you drew from to `sources:` (the path must exist), bump `version` minor once for the whole
  batch, keep the file's formatting, and re-parse it afterwards.
- Scripts: copy an upstream script only if your assignment says so. Keep it stdlib-only where it
  already is, document how to run it, and run it once to prove it executes.

### Report back

1. Write `work/batch-<NNN>/out/<your-id>.json`: a JSON list, one object per assigned cluster:
   ```json
   {"cluster": "...", "verdict": "new|merge|skip", "target": "<category>/<skill> or null",
    "files": ["<paths written, relative to the registry root>"],
    "sources": ["archive/objects/<id>/<file>", "..."],
    "note": "one line: kept / cut / refreshed; for skip, why"}
   ```
   `sources` lists only archive files you actually drew from.
2. Reply compactly: per cluster, the files written, versions refreshed (old -> new), code
   type-checked (how, result), what you cut and why, anything unresolved. No preamble.
