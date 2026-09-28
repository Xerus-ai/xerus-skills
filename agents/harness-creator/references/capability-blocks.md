# Capability blocks

These are reusable patterns for harnesses that plan, implement, review and ship code. Each one came
out of a real pipeline failure. Look through them when you scaffold a pipeline, adopt the ones that
fit, and record each block as adopted or skipped (with a reason) under `capability_blocks:` in the
definition. Recording a skip is as important as recording an adoption: it shows the block was
considered.

## wiring-map (plan section)

**Failure it prevents:** work built in phases gets flagged as dead code. A file is created in task 2
and wired in task 5, and a reviewer running in between sees no importers and recommends deleting it.

Add a table to the plan template. Every artifact the plan creates must say who consumes it and which
task connects it:

```markdown
### Wiring map
| New artifact | Consumed by | Registered in | Wired by task |
|--------------|-------------|---------------|---------------|
| new_module.py | handler.py | app routes | Task 4 |
```

A plan that creates an artifact with no row in this table is incomplete. Reject it at the plan gate.

## unwired-is-not-dead (review rule)

**Failure it prevents:** a review deletes planned work before it is connected.

Add this to the review or verifier checklist. Before recommending that any function, type or file be
removed:
1. Check the plan's wiring map. If a later task wires the artifact, it is **unwired**.
2. Check the open work items in the project's tracker (whatever it uses). If an open item references
   the artifact, it is planned work.
3. Classify it:
   - **unwired**: it exists, and a future task will wire it. Report "wire it", never "remove it".
   - **dead**: no plan entry, no open item, no importer, no caller. Only then is removal on the table.

When in doubt, call it unwired. Carrying an unwired artifact for one more iteration costs less than
deleting it too early.

## execution-mode-gate (between plan and implement)

**Failure it prevents:** the same execution style gets applied to work that needs a different one:
test-first where the tests can't exist yet, or implementation-first on code that is fragile and
already covered by tests.

Infer two things from the plan, then confirm them with the human in a single question:
1. **Test-first or implementation-first**: does the plan create or change tests or test
   infrastructure?
2. **Brownfield or greenfield**: count the create rows against the update rows in the plan's
   files-to-change table. Above roughly 60% updates is brownfield (be conservative, keep the
   existing tests green at every step). Above roughly 60% creates is greenfield.

Record both decisions in the run receipt, so later evidence can show whether the inference was right.

## proof-of-done (ship step)

**Failure it prevents:** "done" with nothing behind it.

Every completion claim produces evidence that fits the kind of work:
- UI work: a screenshot or recording of the main path and the key edge cases.
- API or backend work: a receipt with real request and response bodies, plus the test output.
- Data or migration work: before-and-after counts or queries.

Store the evidence under a per-item directory with a size cap (keep the N most recent). Record the
evidence path in the run receipt. The postcheck should confirm the path exists.

## Patterns that carry over only as ideas

Each of these is worth keeping as a principle, but the implementation depends on the project. Adapt
them rather than copying anyone's version:

- **Route to the right tracker automatically**: work out which issue tracker or project a work item
  belongs to from where the work is happening, instead of asking every time.
- **Choose reviewers by what the diff touches**: pick the specialist reviewers (security,
  performance, data integrity, ...) from the files and areas the diff changes, rather than running
  all of them every time. The routing table belongs to each project.
- **Detect optional tools, then offer or skip**: before a node relies on an optional tool, check
  that it is available. If it isn't, offer to install it or skip the node explicitly, and record the
  skip. Never fail halfway through.
- **Safety-net hooks**: when a workflow is supposed to keep an invariant (every plan has a work
  item, every ship has a receipt), a hook that checks the invariant catches the runs where the
  workflow's prose was not followed.
