# Layout and schemas

Everything lives under one **registry root**: the folder holding your curated skills, grouped
into category folders or kept flat. The layout below is what `scripts/pipeline.py` reads and
writes. Rename nothing unless you also change the constants at the top of the script.

```
<registry root>/
  archive/
    objects/<id>/...        immutable skill trees, id = first 12 hex of a content hash
    manifest.jsonl          one row per captured tree
    clusters.json           normalised name -> [ids]
    ratings.jsonl           optional, one row per cluster (from raters)
    cache/                  derived shingle cache for `overlap`, keyed by object id (safe to delete)
  work/
    batch-001/              shape.md, candidates.json, briefs, W*.json, verifier reports
  decisions.jsonl           append-only decision ledger
  registry-index.json       generated
  <category>/<skill>/
    SKILL.md
    skill.yaml              sidecar (optional for the index, required to cite sources)
    references/ scripts/ ...
```

Discovery rule: a **curated skill** is any folder under the root holding a `SKILL.md`, except
under the top-level `archive/` and `work/`. The scan does not descend into a skill once found,
and skips `.git`, `node_modules`, `__pycache__` and virtualenvs.

## `archive/manifest.jsonl`

One JSON object per line, appended by `capture`, never rewritten:

```json
{"id": "3f9a0c1b2d4e", "name": "db-migrations", "origin": "https://github.com/example/skills",
 "source": "skills/db-migrations", "licence": "MIT", "licence_clear": true,
 "licence_file": "LICENSE", "files": 4, "bytes": 18231, "marker_bytes": 6120,
 "stored": true, "captured_at": "2026-01-15"}
```

| Field | Meaning |
|---|---|
| `id` | sha256 over (relative path, NUL, bytes, NUL) of every file, sorted by path; first 12 hex |
| `name` | frontmatter `name` of the marker file if parseable, else the folder name |
| `origin` | what you passed to `--origin`. Prefer a URL a stranger can follow |
| `source` | path of the tree relative to the captured folder |
| `licence` | permissive: `MIT`, `Apache-2.0`, `BSD`, `ISC`. Copyleft: `GPL`, `LGPL`, `AGPL`, `MPL-2.0`. Source-available / restrictive: `ELv2` (Elastic), `BUSL` (Business Source), `SSPL` (Server Side Public), `Commons-Clause`, `PolyForm`, `FSL` (Functional Source), `SUL` (Sustainable Use), `Confluent` (Confluent Community). Other: `CC`, `mixed:<permissive>+<restrictive...>`, `proprietary`, `unknown`, `none` |
| `licence_clear` | true only for MIT / Apache-2.0 / BSD / ISC |
| `licence_file` | the licence file found, relative to the repo root (or captured folder) |
| `marker_bytes` | size of the marker file. Under ~200 bytes is usually a stub or a pointer |
| `stored` | false when the tree exceeded `--max-bytes`. Such rows cannot be cited |

Licence detection walks UP from the tree to the nearest `LICENSE*` / `LICENCE*` / `COPYING*`,
stopping at the enclosing git repo root (or the captured folder when it is not in a repo). It
classifies by distinctive phrases, most specific first:

- The **title region** (first ~600 characters) is tried before the whole text, because the full
  GPLv3 and MPL-2.0 texts both name the Affero GPL in their body. GPLv3 reads `GPL`, MPL reads
  `MPL-2.0`.
- **Fail closed on mixed files.** If the title region is permissive but the file names any
  non-permissive licence anywhere, the label is `mixed:<permissive>+<every restrictive licence
  named>` and the row is not clear. Examples:
  - MIT text plus "the ee/ directory is under the Elastic License 2.0" reads `mixed:MIT+ELv2`
  - MIT plus a Commons Clause condition reads `mixed:MIT+Commons-Clause`
  - Apache plus a PolyForm Noncommercial directory reads `mixed:Apache-2.0+PolyForm`
  - BSD code that bundles a full GPL text reads `mixed:BSD+GPL-family`

  The GPL variants are collapsed to `GPL-family` inside a mixed label, because the GPLv3 body
  itself names the AGPL and LGPL. Several source-available licences (Commons Clause, SSPL)
  exist precisely to sit on top of OSI text, so a pack licensed MIT at the root with one
  restricted directory is exactly the case this pipeline must not wave through.
- The restrictive list is finite. A licence the script does not know, appended to MIT text,
  still reads as MIT. That is why a human or verifier reads the licence file of everything that
  is promoted (see below). When you meet a new source-available licence, add its name to
  `LICENCE_RULES` in the script.
- `CC` covers every Creative Commons variant; read the file before relying on it.
- `unknown` and `none` are not clear.

A false "not clear" costs a human read. A false "clear" ships someone else's restricted work.
Treat detection as a first filter: a human or verifier still reads the licence text of anything
promoted.

Excluded from capture and hashing: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`,
`.mypy_cache`.

## `archive/clusters.json`

`{"db-migrations": ["3f9a0c1b2d4e", "77c2..."], ...}`, regenerated from the manifest by
`clusters` (deterministic). The normalised name is lowercase with runs of non-alphanumerics
replaced by `-`. Splitting a cluster that holds unrelated skills is recorded in the ledger
`note`, not by editing this file.

## `archive/ratings.jsonl` (optional)

One line per cluster, produced by raters (see `rating.md`):

```json
{"cluster": "db-migrations", "quality": 4, "verdict": "merge", "category": "data",
 "merge_target": "data/database-operations", "summary": "Transactional migration runbook with rollback checks.",
 "reason": "solid, belongs in the existing ops skill", "stale": false}
```

`status --list open` joins it in. The licence is deliberately not a rating field: it comes from
the manifest.

## `<skill>/skill.yaml` (sidecar)

```yaml
name: database-operations
version: 1.2.0
sources:
- archive/objects/3f9a0c1b2d4e/SKILL.md
- archive/objects/3f9a0c1b2d4e/references/rollback.md
- https://example.com/docs/migrations
provenance:
- db-migrations
- schema-rollbacks
```

- `sources:` lists archive files the skill actually drew from (globs allowed) and/or URLs.
  Archive paths must match `archive/objects/<12 hex>/<file>`. Anything else fails `provenance`.
- `provenance:` lists cluster names folded in. Each must exist in `clusters.json`.
- Other keys (owner, status, axes, notes...) are yours. The script only reads `version`,
  `sources` and `provenance`.
- Keep it to top-level scalars, `- item` block lists and one-line flow lists (`[]`, `[a, b]`) if
  PyYAML is not installed. The fallback parser ignores nested mappings and multi-line values.
- If you publish a skill, strip archive-path sources on the way out, or replace them with the
  upstream URLs. Readers of the public copy cannot resolve your archive.

## `decisions.jsonl` (the ledger)

Written only by `ledger-append`, one row per cluster per batch:

```json
{"batch": "003", "cluster": "db-migrations", "date": "2026-02-01", "note": null,
 "target": "data/database-operations", "verdict": "merge"}
{"batch": "003", "cluster": "sheets", "date": "2026-02-01",
 "note": "Elastic License 2.0 - copied nothing; covered by data/spreadsheets written from vendor docs",
 "target": null, "verdict": "skip"}
```

`verdict` is `new` (became or joined a skill created in this batch), `merge` (folded into a skill
that already existed) or `skip` (nothing kept; `note` required). Input to `ledger-append` is a
JSON list of `{cluster, verdict, target, note}`. The command refuses, appending nothing, when:

- the batch id is already present (append-only, never twice)
- a cluster is unknown or appears twice in the file
- a verdict is not new/merge/skip
- a new/merge target has no `SKILL.md` yet (write before you log)
- a skip has no note

`status` reads the ledger with "the latest row for a cluster wins", so re-deciding a cluster is a
new row in a later batch. Never edit old rows.

## `registry-index.json`

`{"count": N, "skills": [{"path", "name", "description", "version", "provenance"}]}`, sorted by
path and deterministic (no timestamp), so it diffs cleanly. `index` refuses to write when any
skill has no or invalid frontmatter, `name` differs from the folder name, the description is
empty or over 1024 characters, or an unquoted `: ` appears in a plain scalar. It also refuses to
write an empty index.

## Subcommand reference

| Command | Passes when | Fails when |
|---|---|---|
| `capture SRC --origin X [--marker F] [--max-bytes N] [--dry-run]` | always, and prints licence tally and stub count | source folder missing |
| `clusters` | manifest non-empty | nothing captured |
| `status [--list open\|covered\|curated\|skipped]` | clusters exist | `clusters.json` missing |
| `ledger-append FILE --batch B [--date D] [--dry-run]` | every row valid | any rule above; appends nothing |
| `provenance [--deep] [--allow-empty]` | every archive citation resolves and >= 1 checked | dangling / unknown id / unstored object / malformed source / unknown provenance cluster / ledger target without SKILL.md / zero checked / (`--deep`) object edited or missing |
| `index` | all curated skills valid | any frontmatter problem; nothing found |
| `overlap SKILL_DIR [--n 8] [--max 25] [--max-unclear 2]` | every text file under both limits | a file over `--max`% of 8-word shingles shared with a cited source; over `--max-unclear`% with any non-clear archive file, cited or not; no file long enough to compare; nothing to compare against; skill folder not found |

Relative `FILE` (ledger-append) and `SKILL_DIR` (overlap) arguments are tried against the current
directory first, then against `--root`. A path found in neither fails with a one-line error.

`overlap` compares word 8-grams of each text file in the skill (excluding `skill.yaml`) against
two sets. "Text file" means any file without a NUL byte in its first 8 KB, whatever its
extension, so a cited `.html` or `.csv` source is compared like a `.md` one. Only binaries
(images, archives, fonts) are skipped, since they carry no copyable prose.

1. **Cited sources**: every archive file matched by the skill's `sources:`. Over `--max` means
   pasting (fold, don't paste); over `--max-unclear` against a non-clear cited source is a licence
   problem.
2. **Every stored archive file whose licence is not clear**, cited or not. A writer who copies
   from a tree it was told to copy nothing from will not cite it, so a gate limited to citations
   compares the paste against nothing and passes. Any uncited match over `--max-unclear` fails as
   `uncited overlap with <file> (licence not clear: <licence>)`.

URL sources are counted in the output but not compared. A skill written fresh, with no archive
sources, is still checked against set 2. For reference, a well-folded batch measured at most ~8%
overall and ~2% in prose. Code blocks and API names overlap legitimately. High prose overlap
means pasting.

Each failure line ends with up to two of the shared 8-word phrases (`e.g. "..."`), so whoever
rules on it can see *what* matched without diffing files by hand.

**Cost on large archives.** Shingling is the expensive step, so each object's shingles are cached
as 64-bit hashes in `archive/cache/shingles-n<N>/<id>.json`. The entry stores the tree hash of
the files it was built from and a digest of its own contents. On every run, `overlap` recomputes
each object's tree hash (a plain sha256 over its bytes, cheap next to shingling) and uses the
entry only if both match. It rebuilds the entry if any of these happened:

- the object was edited, or edited and later restored
- the entry was hand-edited
- the entry is truncated or unreadable

The cache can therefore be deleted at any time but never needs to be. It cannot make `overlap`
compare against text that is no longer on disk. If an object's current hash differs from its
id, `overlap` also reports `object <id> edited since capture`, and `provenance --deep` drops that
object's cache entries. The first run on a big archive pays the full read; later runs pay only
the hashing. The digest catches accidents, not a deliberate forgery by someone who recomputes it.
The archive and its cache are trusted in the same way as the rest of your repo.

**False positives.** Fresh text can legitimately share 8-word runs with an unclear-licence file:
the same CLI invocation, a standard config block, an error string quoted verbatim from the
vendor. The gate does not guess. It fails, and the verifier rules from the evidence it prints
(see the verifier brief, "Waiving an overlap finding"). Never raise `--max-unclear` for a whole
run to get one file through.
