# Design guidance for the artifact

The artifact is a document someone will *read*, probably more than once, possibly offline and on a
phone. Design for reading and re-finding, not for a first-impression wow. These rules are opinionated
on purpose; break one only when you can say why this video needs it.

If a design-taste or frontend-design skill is installed in the environment, apply it as well. Where
it conflicts with the offline and honesty rules here, these win (the checker enforces them).

---

## 1. Layout: one reading column

- Body text column 62-72 characters wide (`max-width: 68ch`). Body size 17-19px, line-height 1.55-1.65.
- Wide screens (roughly 1100px and up): a sticky contents rail on the left, the reading column beside
  it. Narrow screens: contents collapse into a `<details>` block under the header. CSS cannot force a
  closed `<details>` open, so emit the contents twice: `<nav class="toc">` (the rail, hidden below
  1100px) and `<nav class="toc-narrow"><details><summary>Contents</summary>...</details></nav>`
  (hidden above it). The starting stylesheet in section 7 does exactly this.
- Hierarchy comes from size, weight and space. Separate sections with generous space and, at most,
  a hairline rule. Do not put every section in a box.
- Pick the macro-shape from the content, not habit:
  - **Long read** (default): talks, interviews, essays-on-video.
  - **Step sequence**: tutorials and walkthroughs; the techniques section leads, numbered.
  - **Catalogue**: framework-dense videos; a compact index of frameworks up top, detail below.
  - **Argument**: opinion pieces; open with the thesis and the strongest claims, then the evidence.

## 2. Type: offline-safe stacks, two families at most

Never link web fonts: it adds an external request, breaks offline use, and the checker fails it.
Choose one pairing per artifact:

| Content | Body | Headings | Code / timestamps |
|---|---|---|---|
| Ideas, strategy, interviews | `Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif` | same serif, heavier | mono |
| Technical, tools, demos | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` | same sans, heavier | mono |
| Mixed | serif body | sans headings | mono |

Mono stack: `ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace`.

- A modular scale around 1.25. `h1` about `clamp(2rem, 5vw, 3.2rem)`, slight negative tracking on
  large headings (`-0.015em`), `text-wrap: balance` on headings.
- `font-variant-numeric: tabular-nums` on timestamps and anything counted.
- Small uppercase labels (letter-spaced ~0.08em) are for metadata only, not for headings.

## 3. Colour: paper, ink, one accent

- Define everything as CSS custom properties on `:root`. Background slightly warm or cool off-white,
  not `#fff`; text a very dark tinted neutral, not `#000`.
- **One** accent hue, chosen to suit the subject, used only for links, timestamps and the active
  contents item. A second, muted "caution" hue is allowed for anti-pattern labels. Nothing else is
  coloured.
- Provide a dark scheme with `@media (prefers-color-scheme: dark)` using its own tuned values
  (lower-chroma accent, dark-grey not black paper). Do not just invert.
- Body text contrast at least 4.5:1 in both schemes; muted text at least 4.5:1 too, it is still text.
- `oklch()` is fine (all current browsers); hex is fine. Consistency matters more than the space.

## 4. Components

- **Timestamp link**: mono, small, accent colour, tabular numbers, e.g. `12:34`. Opens the video at
  that second in a new tab (`https://www.youtube.com/watch?v=ID&t=754s`, `rel="noopener"`).
  Place it at the start of the thing it anchors, consistently.
- **Pull quote**: `<blockquote>` for verbatim words only. Larger than body, a hanging opening quote
  mark, the timestamp link beneath. Two or three per topic section at most; a page of quotes is a
  transcript, not an analysis.
- **Framework / technique**: `<details>` whose `<summary>` shows the name and a one-line gist; steps
  as an `<ol>`. Open the first one by default. These are the only card-like objects on the page, and
  they should be quieter than the headings around them.
- **Anti-pattern**: the same shape with a small "Avoid" label in the caution hue and a faint tinted
  background. Do not turn the whole card red.
- **Diagram**: inline `<svg>` with a `viewBox`, `max-width: 100%`, strokes and fills using
  `currentColor` or the CSS variables so it follows dark mode; labels as real `<text>`. Caption it
  with what it shows and when.
- **Code**: `<pre><code>`; the block scrolls horizontally, the page never does.
- **Embedded frame** (only when a recreation would lose information, e.g. a dense UI): a `<figure>`
  with a base64 JPEG downscaled to 960px wide or less, a caption with its timestamp, and alt text that
  describes the content, not "screenshot". Keep the whole file under about 3 MB.

## 5. Behaviour

- Everything must work with JavaScript off. `<details>` handles expand/collapse natively.
- Optional small inline script: highlight the current section in the contents rail, and open all
  `<details>` on `beforeprint`. No libraries, no CDN.
- Smooth scrolling only inside `@media (prefers-reduced-motion: no-preference)`. No entrance
  animations, parallax or hover effects that move layout.
- Visible focus styles on every link and summary.
- Print: hide the contents rail, black on white, keep timestamps.

## 6. Tells of a machine-made page (do not ship these)

- Emoji as icons or section markers.
- A gradient hero banner, or a purple-to-blue anything.
- Everything centred; or every section in an identical card; or rows of three equal cards with an
  icon, a title and a vague sentence.
- Filler headings ("Introduction", "Key Takeaways", "Conclusion") where a specific heading that says
  what the section concludes would do: "Retrieval beats fine-tuning below 10k documents".
- Numbers, stats or "impact" figures that are not in the video.
- Shadows, rounded corners and badges on everything. Pick one small radius and use borders sparingly.
- Headings that are questions the section then doesn't actually answer.

## 7. Starting stylesheet

A compact base to adapt (change the pairing, accent and spacing to fit the video; do not ship it
unmodified every time):

```css
:root {
  --paper: oklch(98.5% 0.006 85); --ink: oklch(24% 0.015 260); --muted: oklch(46% 0.015 260);
  --rule: oklch(88% 0.01 85); --accent: oklch(52% 0.13 40); --caution: oklch(55% 0.14 65);
  --tint: oklch(96% 0.012 85);
  --body: Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  --ui: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace;
  --s1: .25rem; --s2: .5rem; --s3: 1rem; --s4: 1.5rem; --s5: 2.5rem; --s6: 4rem;
}
@media (prefers-color-scheme: dark) {
  :root { --paper: oklch(20% 0.01 260); --ink: oklch(92% 0.01 85); --muted: oklch(72% 0.01 85);
          --rule: oklch(32% 0.01 260); --accent: oklch(74% 0.1 45); --caution: oklch(78% 0.11 75);
          --tint: oklch(24% 0.012 260); }
}
* { box-sizing: border-box; }
html { background: var(--paper); color: var(--ink); }
body { margin: 0; font: 1.075rem/1.6 var(--body); overflow-wrap: break-word; }
.page { display: grid; gap: var(--s5); max-width: 76rem; margin: 0 auto; padding: var(--s5) var(--s3); }
@media (min-width: 1100px) { .page { grid-template-columns: 14rem minmax(0, 68ch); }
  nav.toc { position: sticky; top: var(--s4); align-self: start; } }
main { max-width: 68ch; min-width: 0; }  /* min-width: 0 stops a long <pre> widening the grid */
nav.toc-narrow { margin-bottom: var(--s4); }
@media (min-width: 1100px) { nav.toc-narrow { display: none; } }
@media (max-width: 1099px) { nav.toc { display: none; } }
h1, h2, h3 { line-height: 1.15; letter-spacing: -0.015em; text-wrap: balance; }
h1 { font-size: clamp(2rem, 5vw, 3.2rem); margin: 0 0 var(--s3); }
h2 { font-size: 1.6rem; margin: var(--s6) 0 var(--s3); }
.meta, .label { font: 600 .75rem/1.4 var(--ui); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
a { color: var(--accent); text-underline-offset: .15em; }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.ts { font: .8rem var(--mono); font-variant-numeric: tabular-nums; text-decoration: none; }
blockquote { margin: var(--s4) 0; padding-left: var(--s4); font-size: 1.25rem; line-height: 1.45; text-indent: -.45em; }
blockquote::before { content: "\201C"; color: var(--muted); }
details { border-top: 1px solid var(--rule); padding: var(--s3) 0; }
summary { cursor: pointer; font-weight: 600; }
.avoid { background: var(--tint); padding: var(--s3); border-radius: 4px; }
.avoid .label { color: var(--caution); }
pre { overflow-x: auto; padding: var(--s3); background: var(--tint); font: .85rem/1.5 var(--mono); }
svg { max-width: 100%; height: auto; }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
@media print { nav.toc, nav.toc-narrow { display: none; } html { background: #fff; color: #000; } }
```

## 8. Self-review before handing over

1. Squint at the page: can you see the section structure without reading a word?
2. Narrow the window to about 360px: no horizontal page scroll, contents collapsed, diagrams scale.
3. Dark scheme: every colour, including inside SVGs, still reads.
4. JavaScript off: nothing missing.
5. Run `scripts/check_artifact.py` and fix every FAIL.
6. Would a stranger guess a template made it? If yes, change the pairing, the accent, or the shape.
