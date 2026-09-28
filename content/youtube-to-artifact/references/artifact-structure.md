# Artifact structure

One self-contained HTML file: inline CSS, optional inline JS, no external resources. The sections below
are the content model; how they look is in `design.md`. Adapt the set to the chosen depth (bottom of
this file). Omit a section that would be empty rather than padding it.

---

## Sections

### 1. Source header
Video title as the page's only `<h1>`, channel, upload date, duration, a "Watch on YouTube" link, and
the analysis date. If the analysis is degraded (no transcript, no frames, a section only), say so here
in one plain line.

### 2. Summary
Two or three sentences: the video's thesis and why it matters. The 10-second version.

### 3. Contents
Anchor links to every section; topic entries carry their timestamp range.

### 4. Topic sections
One per major topic, in video order. Each has:
- a heading that states what the section concludes, plus its timestamp range as a link
- key points (a short list)
- pull quotes: verbatim only, each with its timestamp link
- visual anchors: what was on screen (recreated diagram, code block, or a short description of the UI)
- visual-only notes: anything shown but never said aloud (menu paths, on-screen code, error text)

If the video has chapters (`metadata.json` -> `chapters`), use them as the first cut of topics.

### 5. Frameworks
Named mental models. Per framework: name, origin (who coined it, if stated), when to use it, steps,
the example from the video, timestamp.

### 6. Principles
Decision rules the speaker states. Per principle: the rule (in the speaker's words when they said it
crisply, otherwise marked as your paraphrase), when it applies, their reasoning, stated exceptions.

### 7. Techniques
Step-by-step methods shown or described. Per technique: prerequisites, numbered steps, pitfalls,
what success looks like, and a recreated visual if the demo was visual.

### 8. Anti-patterns
What to avoid. Per item: the pattern, why it fails, what to do instead, how to spot it in your own work.

### 9. Recommendations and debates
Things the speaker explicitly endorses; where they push back on conventional wisdom and why; trade-offs
they lay out. If research found counter-evidence, put it here, attributed to its source.

### 10. Resources
Every link from the description plus tools, repos, papers and products mentioned or shown. Per item:
title, URL, why it is relevant, a 2-3 sentence summary if it was fetched, otherwise "not fetched". For
repos: stars, main language, last update, as of the analysis date.

### 11. Voice profile
Short: recurring phrases, reasoning style (first-principles, analogical, experiential, data-driven),
where they are emphatic vs hedged, delivery style (lecture, demo, conversation, story).

### 12. Attribution footer
"Analysis of [title] by [channel]", the URL, the analysis date, the method (transcript + N frames, or
whichever channels were actually used).

---

## Depth

| Depth | Include |
|---|---|
| **Brief** | Header, summary, 5-8 key takeaways (each with a timestamp), the top 3 frameworks or techniques, resources list (unfetched is fine), footer |
| **Detailed** (default) | All sections |
| **Exhaustive** | All sections, plus: every substantive quote, frame-by-frame notes in an appendix, a cleaned transcript with visual annotations at the moments frames were read, cross-references from each framework to every moment it comes up |

## Honesty rules (these are not style)

- Every factual claim about the video traces to a timestamp.
- `<blockquote>` holds verbatim transcript text only; elide with an ellipsis if needed, but every
  fragment must be the caption's words in order. Auto-captions can mishear: if the caption text is
  garbled, paraphrase outside a blockquote rather than "correcting" it inside one (the checker compares
  blockquotes against the transcript). Put the timestamp link after the `</blockquote>`, not inside it.
- Your own inferences, opinions and research go under a clear label ("Analyst note", "From the linked
  paper"), never blended into what the speaker said.
- Never invent numbers, names or links. An unfetched resource says "not fetched".
