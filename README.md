# Xerus skills

Skills authored by the Xerus team for Claude Code and other agents that read `SKILL.md`. Each folder is self-contained: copy it into your project's `.claude/skills/`.

| Skill | Category | What it does |
|---|---|---|
| [`ai-music-generation`](content/ai-music-generation/SKILL.md) | content | Generate music with Google's Lyria models through the Gemini API - instrumental beds, loops, soundtracks and game audio with Lyria RealTime (weighted prompt blending, BPM, key/scale, density, brightness, temperature, QUALITY/DIVERSITY/VOCALIZATION mode) rendered to a 48 kHz stereo WAV by scripts/lyria.py, and full songs with vocals and lyrics with Lyria 3.5 / Lyria 3 Clip |
| [`merge-and-preserve`](dev/merge-and-preserve/SKILL.md) | dev | Merge parallel branches without losing tests, wiring, plan/work-item references, or integration state |

Licensed under the MIT License - see [LICENSE](LICENSE).

_This repository is generated; changes are made upstream and exported._
