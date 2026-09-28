# Verifier and fixer briefs

## Why default-REJECT, and why a fresh context

The agent that wrote a batch has already decided it is right. It re-reads its work through
that decision and finds what it expects. The verifier must be a separate context (a new
subagent or a new session) that never saw the writing. Its starting verdict is REJECT, and each
check must earn its way to PASS with evidence. A verifier that "mostly agrees" is doing a
writer's review, not verification.

## Verifier brief (template)

```
You are the independent verifier for promotion batch <NNN> (<theme>) in <registry root>.
Your verdict starts at REJECT. Move to ACCEPT only if every check below PASSES with evidence you
gathered yourself. You are READ-ONLY on the registry. You may create a scratch folder at
<work/batch-NNN/verify/> for type-check projects and unpacked packages. Delete nothing else.

Inputs: the approved shape (work/batch-<NNN>/shape.md), the writer brief, the writers' reports
(work/batch-<NNN>/out/*.json), and the list of files changed.

Checks:
1. LICENCE. For each source cited, open the licence file named in archive/manifest.jsonl and
   confirm the class yourself. Run `pipeline.py overlap <skill>` for every touched skill. Report
   the max % per file. Prose copied from a non-permissive source is blocking at any size above
   incidental phrases.
2. PROVENANCE. `pipeline.py provenance` passes and reports a non-zero count. Sample 5 cited
   sources: was each actually used? Were real sources left uncited?
3. CORRECTNESS. For every code block in a typed ecosystem: unpack the real package at the stated
   version and strict-type-check the block (see code-verification.md). Check at least <N> factual
   claims (limits, defaults, status) against official docs. Check security-relevant code line by
   line: token/signature verification, audience/issuer checks, access control, secret handling.
4. FRONTMATTER / INDEX. `pipeline.py index` passes. Each description says what AND when.
5. SCOPE AND SHAPE. Files changed match the writers' lists; the shape was followed; nothing
   outside the batch changed (compare against version control if available).
6. SKIPS. Every skip has a reason that holds when you read the body.
7. CLAIMS. Each "verified against" line is plausible for what you found.

Output: write your full report to work/batch-<NNN>/verify/R<round>.md and reply with a summary.
Report format:
  VERDICT: ACCEPT | REJECT
  Per check: PASS / FAIL + evidence (commands run, counts, file:line).
  Findings, numbered, each: severity (BLOCKING = wrong, insecure, or licence; FIX = quality),
  file:line, what is wrong, evidence, suggested correction.
  Mark every suggested correction you did NOT type-check or test as "unchecked".
```

Ask for the long report in a file and a short reply. Long subagent replies get truncated.

## Fixer brief (template)

```
You fix findings from verifier round <R> of batch <NNN>. Your files (write ONLY these): <list>.
Your findings: <numbers from R<R>.md>.

For each finding:
- Reproduce it first. Re-check the claim against the real package types / official docs yourself.
  Do not take the verifier's word, numbers or code on trust.
- If it holds: fix it. If the verifier suggested code, type-check or test that code before using it.
- If it does not hold: DISPUTE it with evidence (command output, file:line in the package types,
  doc URL). Do not change the file.
- Note anything else wrong that you find on the way. Fixers who verify find more than they were sent for.

Same hard rules as the writer brief: your files only, delete only what you created by exact name,
no version-control changes, frontmatter/skill.yaml re-parsed after editing.

Reply per finding: FIXED (evidence) | DISPUTED (evidence) | EXTRA (new defect found + fix).
```

## Waiving an overlap finding

`overlap` fails closed at a low threshold, so a writer working fresh from vendor docs can trip it
on text neither copied: the same CLI line, a standard config block, a verbatim error string. Only
the verifier may waive such a finding, only from evidence, and never silently:

1. Read the shared phrases the failure line prints (`e.g. "..."`) and open both files at those
   phrases.
2. Waive only if every shared run is **functional or factual text that cannot be phrased another
   way**: commands, code identifiers, config keys, API names, quoted error messages, licence
   boilerplate. Any shared **prose** (explanation, advice, structure of an argument) is not
   waivable. It is blocking, and the fix is a rewrite.
3. Record the waiver in the round report under `WAIVERS`, one entry each: skill file, archive
   file, percentage, the shared phrases, the reason, and your verdict. Copy the same line into
   the ledger `note` of the affected cluster(s) when the batch is logged.
4. Re-run `overlap` after any fix. A waiver covers the exact file and percentage recorded. If the
   number rises, the waiver is void.

Never pass a higher `--max-unclear` to make a run green. A waiver is scoped to one file; a
threshold change silently waives every file in the run.

## Running the rounds

1. R1: full verification. Expect REJECT on a first round. That is normal and the point.
2. Fix wave: split findings across fixers by file (disjoint). Rule on disputes by evidence.
3. R2..R3: re-verify the changed files plus anything they touch. Resuming the same verifier is
   fine; it keeps its unpacked packages and context.
4. After R3 without ACCEPT the batch is `exhausted`: drop or hold the failing skills, log only
   the accepted part (itself re-verified), and tell the human what is held and why.

Typical R1 blocking findings from real batches, in rough order of frequency: removed or renamed
exports used in examples; wrong function signatures after a major version; security examples that
look right and are not (an HS256 "verify" against a public keys URL that accepts forged tokens,
middleware with no audience check); invented endpoints in upstream material; stale limits.
