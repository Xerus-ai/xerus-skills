# Gathering source material

Three input doors, freely mixed. A course built from a mix (a couple of videos, the team's own
notes, and a topic to fill gaps) is usually the best one. Whatever the door, the output of
gathering is the same: a list of **what was actually read**, and the frameworks, principles,
techniques, examples and anti-patterns found in it.

## Reuse before re-extraction

Before extracting anything, look for work already done on the same source:

- an existing course in the courses root whose `sources:` lists the same URL or file;
- files in `{course}/sources/` of an earlier course;
- notes, summaries or HTML write-ups elsewhere in the repo that name the URL (search the repo
  for the video id).

If a finished extraction exists, read it and harvest from it instead of paying for the same
transcript pass again. Record in the index `## Provenance` which lessons came from reused
material and which from fresh extraction.

## Door 1: YouTube URLs

Accept any number of URLs (comma, space or newline separated). For each, in order of preference:

1. **If a video-analysis skill such as `youtube-to-artifact` is installed**, use its extraction
   steps for the transcript and knowledge pass. Tell it the focus is "frameworks and techniques,
   detailed" so it does not ask its own questions per video, and skip its own page/artifact
   output: the course is the output.
2. **Otherwise extract the transcript directly**, feature-detecting tools:
   - `yt-dlp` on PATH:
     ```
     yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "en,en-orig" --sub-format vtt -o "{course}/sources/%(id)s" URL
     ```
     List languages explicitly; never use a regex like `en.*`. It also matches YouTube's
     auto-translated tracks (`en-es`, ...), which YouTube commonly rate-limits (HTTP 429), so
     yt-dlp exits non-zero even though the English file was written. If a video only has a
     regional manual track, add it explicitly (`en,en-orig,en-US,en-GB`).
     **Judge success by whether an `ID.en*.vtt` file exists, not by the exit code.** If both
     `ID.en.vtt` and `ID.en-orig.vtt` exist, clean `ID.en.vtt` and delete the other; otherwise
     clean whichever `ID.en*.vtt` exists (e.g. `ID.en-orig.vtt` or `ID.en-US.vtt`). Clean with:
     `python .claude/skills/course-builder/scripts/vtt_to_text.py {course}/sources/{that .vtt file} --out {course}/sources/ID.md`
     (removes rolling-caption duplicates and timing tags, keeps a `[mm:ss]` marker each minute).
     `yt-dlp --print title --print channel --print duration URL` gives metadata.
   - Python package `youtube_transcript_api` importable: fetch the transcript segments and write
     them to `{course}/sources/ID.md` in the same `[mm:ss]` paragraph style. The API changed
     between versions: 1.x is `YouTubeTranscriptApi().fetch(video_id)` (segments have `.text` and
     `.start`), 0.6.x is `YouTubeTranscriptApi.get_transcript(video_id)` (dicts with `text` and
     `start`). Old installs often fail against today's YouTube (e.g. an XML `ParseError`). **Any
     exception means fall through to the next option**; do not debug the library.
   - Neither available: say so, and ask the user to paste the transcript (or install one of the
     two). Do not guess a video's content from its title.
3. **Read the transcript, not a summary of it.** Pull out: the claims, the frameworks and named
   techniques, the worked examples, the warnings and anti-patterns, and where (timestamp) each
   came from.

Failure handling: rate limits, missing subtitles, private or removed videos. Retry once, then
move on. A course ships from what extracted; the gap goes in `## Provenance`
("video 3 had no captions; lesson 4 is thinner as a result"), never papered over with filler.

Keep the cleaned transcripts in `{course}/sources/` when they were produced. They are provenance
the tutor can quote from later, and they make a rebuild cheap.

## Door 2: local documents and notes

Any files or folders the user points at: Markdown, text, code, PDFs, slide exports.

- Read them fully; for a folder, list it first and read what is relevant to the course, saying
  what was skipped.
- PDFs and office files: use whatever reader is available (a PDF skill, `pdftotext`, a Python
  library). If none can read a file, list it as unread in `## Provenance`.
- Cite them in `sources:` by repo-relative path (or by file name if outside the repo). Do not copy
  them into the course folder; quote short passages in lessons where it helps.
- The user's own notes often contain the most valuable material for them: their examples, their
  terms, their mistakes. Prefer their vocabulary over a textbook's when both are correct.

## Door 3: a topic

A topic with no sources ("teach me consistent hashing") is built from, in order:

1. material already in the repo (search for the topic's key terms: docs, READMEs, code, ADRs);
2. web search and fetch, **if** those tools are available — cite every page actually read;
3. general knowledge, cited honestly as the literal source `model-knowledge`.

Topic mode is where invented citations happen. A source appears in `sources:` only if it was
opened and read during this build. "I believe this comes from X" is `model-knowledge`, not X.

## Provenance summary

By the end of gathering you should be able to fill in, for every planned lesson, which sources
it draws from. If a lesson has no source except `model-knowledge` in a course that was meant to be
built from the user's material, flag that in the plan: it may be a lesson the material does not
support.
