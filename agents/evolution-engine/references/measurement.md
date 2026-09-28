# Measurement discipline

## Proposal-quality checks (do these before `evo.py propose`)

1. **Confirm the diagnosis directly.** If the hypothesis says "the agent fails because X is empty /
   missing / misconfigured", check X yourself before proposing. Plans and earlier sessions state
   root causes that turn out to be false; a fix built on a false cause can be actively harmful (for
   example, a prompt rule telling the agent "if the search returns nothing, the thing does not
   exist" - when the real cause was that the index was never populated - turns a data bug into the
   agent confidently denying things that exist).
2. **Back-test the gate criteria.** Apply the proposed criteria to the history you already have.
   Would they have flagged the incident that motivated the proposal? If a known-bad period would
   have passed, the criteria cannot detect the problem. Test against the real past, not an invented
   scenario - invented scenarios tend to be shaped to pass.
3. **Make sure the metric can go red.** Before trusting a metric, see it fail at least once, on real
   or deliberately seeded bad input. A metric (or check) that has only ever been observed passing
   may be structurally unable to fail.
4. **Measure where the failure lands.** If the failure mode writes to five places and the metric
   looks at one, the metric will certify the failure. List where the failure shows up and measure
   there.
5. **Prefer enforcement to prose when prose already failed.** If the evidence is "the rule exists and
   was ignored N times", the hypothesis "a stronger-worded rule will be followed" needs extra
   scrutiny. A deterministic check is often the better single variable.

## Choosing N

- Floor: 3 runs. Nothing gets a verdict below that.
- Frequently-run or noisy targets (per-commit hooks, pipelines with variable task mix): 5 or more.
- Rare, high-stakes targets (a weekly loop): 3 may be all you can get in a reasonable window - say
  so and keep the verdict's confidence low.
- A `reverted` verdict needs no minimum: a clear regression is rolled back at once.

## Small-N honesty

Report the number, the N and the spread, not just an average. Good: "retries 3, 1, 1, 2, 1 (mean 1.6)
vs baseline mean 3.1 over 8 runs; low confidence, directionally better". Bad: "retries dropped 48%".
If the gate criteria were met at N=5 but one run was an outlier in either direction, say which.

## Confounders

Record with `--note` anything else that changed during the measurement window:
- model or tool version upgrades
- a different kind of task than the baseline covered
- other edits to the agent setup (on any target) that could plausibly interact
- the human changing how they review or intervene

If a confounder is large (model upgrade mid-window), the honest verdict may be to extend
measurement or revert and re-run later - not to claim improvement.

## Worked example

Target: a review subagent's prompt. Evidence from the last 10 PRs: 31 findings raised, 19 dismissed by
the human as not applicable (61% dismissed) - source: PR review threads #212-#221. Baseline: 61%
dismissal, 3.1 findings/PR, 2 real bugs later traced to those PRs.

- variable: the "what counts as a finding" paragraph in the reviewer prompt
- parameters_cited: check_precision, output_quality
- min_n: 5
- improved: dismissal rate <= 35% over 5 PRs AND bugs traced to reviewed PRs not above baseline rate
- no_change: dismissal rate between 35% and 61%, no rise in traced bugs
- reverted: any rise in traced bugs, OR dismissal rate above 61%

Five PRs later: 12 findings, 3 dismissed (25%); 0 traced bugs so far. Verdict `improved`, noted as
provisional on traced bugs because bugs surface late - revisit in the next review.
