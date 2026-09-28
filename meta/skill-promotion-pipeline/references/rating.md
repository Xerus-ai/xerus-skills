# Rating clusters

Rating turns an archive of thousands of objects into a ranked, filterable pool. Skip it for an
archive of a few dozen. There, triage the candidates directly inside the batch.

## The bar

**Quality 1-5**: does the body beat what a capable model does unprompted?

| Score | Means |
|---|---|
| 5 | Expert procedure with specifics the model lacks: exact error strings and fixes, limits, decision tables, working scripts |
| 4 | Solid and clearly useful. Some specifics, a real procedure |
| 3 | Decent but generic. Mostly what the model would write anyway |
| 2 | Thin: a few bullets, a wrapper around one command |
| 1 | Stub, broken, pointer to another file, or marketing |

Also weigh: deterministic (checklists, scripts) over vibes, and current over stale.

**Verdict**

- `promote`: q4-5 AND not covered by an existing curated skill. A good skill in a niche domain
  with no matching category is still `promote`. Pick the nearest category. Never skip a q4-5
  skill because nothing fits.
- `merge`: q3-5 and its useful part belongs inside an existing curated skill. `merge_target`
  must be the exact path of that skill.
- `skip`: q1-2; routers and index skills; thin vendor curl wrappers; sub-commands of another
  tool; stack-pinned boilerplate the model writes unprompted; duplicates of curated content;
  anything whose purpose is defeating safety measures.

## Rater brief (copy, fill the angle brackets)

```
You rate archived skill clusters so a later promotion batch knows what is worth curating.
You are READ-ONLY everywhere except ONE output file: <absolute path of out-NN.jsonl>.
Do not write anywhere else: no temp files, no archive edits. No version-control commands that change anything.

Inputs:
- Your shard: <path of in-NN.json>, a list of {cluster, objects: [{id, read, marker_bytes}]}.
  `read` is the marker file path relative to <registry root>. Objects are sorted largest first.
- Existing curated skills: <path of a one-line-per-skill list: "path :: description">. Read it once, first.

For every cluster: read the `read` file of up to 3 objects. Judge from the BODY, never the name.
If a body is a stub, empty, or only points elsewhere, say so in `summary`.
Apply the quality scale and verdict rules below. <paste "The bar" section>

Output: one JSON object per line, one line per input cluster, nothing else:
{"cluster": "<exact input name>", "quality": 4, "verdict": "merge", "category": "<one of: ...>",
 "merge_target": "<exact curated path or null>", "summary": "<one sentence: what the body actually contains>",
 "reason": "<one short clause>", "stale": false}
`stale` = true if it asserts outdated models, APIs or versions.
Write the whole file once at the end, as UTF-8 JSON Lines, then read it back and check the line count
equals your shard's cluster count.
Finish with a 3-line report: clusters rated, verdict counts, anything odd.
```

Do **not** give raters the licence to output. The licence comes from the manifest. A rater may
see it as context, but a model-written licence field eventually disagrees with the file.

## Running a rating pass

1. Shard the open clusters (30-40 per shard) into `work/rate/in-NN.json`.
2. **Pilot one shard.** Read its output against the bodies yourself. Typical first-shard defects:
   skipping good niche skills, rating routers highly for their routing prose, trusting the name.
   Tighten the brief, then fan out the rest in waves of <= 10.
3. **Validate every shard** before merging (a short script is enough):
   - each input cluster appears exactly once; no extra clusters
   - every line parses; `quality` in 1-5; `verdict` in promote/merge/skip
   - `merge_target` is null unless merge, and when merge it names an existing curated skill
   Fix the few defects by hand. Re-rating a whole shard to fix three lines wastes the good ones.
4. Concatenate into `archive/ratings.jsonl`.
5. Flag for human re-review: skips rated q4-5 (often vendor-locked but excellent), and every
   `promote` with an unclear licence (usable only by writing fresh from vendor docs).

## What ratings are not

A rating is a pointer to where to look, not a decision. The decision is made in a batch by a
writer who reads every object in the cluster, and it is recorded in the ledger. Expect 10-20% of
`promote` ratings to become merges or skips once a writer sees the whole cluster.
