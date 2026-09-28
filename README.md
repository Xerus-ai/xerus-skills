# Xerus skills

Skills authored by the Xerus team for Claude Code and other agents that read `SKILL.md`. Each folder is self-contained: copy it into your project's `.claude/skills/`.

| Skill | Category | What it does |
|---|---|---|
| [`evolution-engine`](agents/evolution-engine/SKILL.md) | agents | Evidence-driven change cycle for any AI agent setup - prompts, CLAUDE.md/AGENTS.md rules, hooks, skills, subagent definitions, loop or cron configs |
| [`harness-creator`](agents/harness-creator/SKILL.md) | agents | Create, update, modify, or retire an agent harness through governed intake |
| [`loop-creator`](agents/loop-creator/SKILL.md) | agents | Scaffold a contracted, auditable autonomous agent loop in any repository: assess the environment first, get the design approved, then create a CONTRACT (goal, scope, Observe->Choose->Act->Verify->Record workflow, hard stops, token/time budget), a receipts file, a findings table, a registry row under a global pause flag, and a trigger plan - then do the first manual run |
| [`ai-music-generation`](content/ai-music-generation/SKILL.md) | content | Generate music with Google's Lyria models through the Gemini API - instrumental beds, loops, soundtracks and game audio with Lyria RealTime (weighted prompt blending, BPM, key/scale, density, brightness, temperature, QUALITY/DIVERSITY/VOCALIZATION mode) rendered to a 48 kHz stereo WAV by scripts/lyria.py, and full songs with vocals and lyrics with Lyria 3.5 / Lyria 3 Clip |
| [`course-builder`](content/course-builder/SKILL.md) | content | Compose a structured, tutor-ready course from YouTube URLs, local documents/notes, and/or a bare topic: a course folder in the repo (default courses/{slug}/) with an index (objectives, lesson list, concept map), numbered lesson files, a tutor-facing assessment bank (free-recall probes + rubrics per concept), and a practicum spec, plus an optional compiled single-file HTML version |
| [`practicum`](content/practicum/SKILL.md) | content | Runs a course's practical task |
| [`teach-me`](content/teach-me/SKILL.md) | content | Interactive tutor over a course folder (index.md + numbered lessons + assessment.md, as written by a course-builder skill or by hand) |
| [`youtube-to-artifact`](content/youtube-to-artifact/SKILL.md) | content | Turns a YouTube video into a deep, self-contained HTML analysis page by reading BOTH channels: the timestamped transcript (what was said) and extracted frames (what was shown - slides, code, UI, diagrams) |
| [`merge-and-preserve`](dev/merge-and-preserve/SKILL.md) | dev | Merge parallel branches without losing tests, wiring, plan/work-item references, or integration state |
| [`skill-promotion-pipeline`](meta/skill-promotion-pipeline/SKILL.md) | meta | Turn a large pile of collected third-party or candidate agent skills into a small, curated, licence-clean registry, one reviewed batch at a time: capture sources immutably with provenance, cluster duplicates, rate from the bodies, agree each batch's shape with the human, fan out writers on disjoint files, gate with an independent default-REJECT verifier and fix waves, record every verdict in an append-only decision ledger, rebuild the index, and prove no citation dangles |
| [`session-handoff`](ops/session-handoff/SKILL.md) | ops | Write a handoff document at the end of a long agent session so a fresh session with no memory can resume correctly: human rulings in force (dated, including what was explicitly NOT approved), verified per-repo state (commit, branch, remote, pushed or not, dirty files), what the session did, ordered next steps marked by which need an explicit human go, recipes that worked, lessons that cost time, and exact start-up steps |
| [`workspace-cleanup`](ops/workspace-cleanup/SKILL.md) | ops | Safely clean up a sprawling repository or multi-project workspace (stray folders, duplicate copies, stashes, dead docs, crash dumps, misplaced files) without losing anything |

Licensed under the MIT License - see [LICENSE](LICENSE).

_This repository is generated; changes are made upstream and exported._
