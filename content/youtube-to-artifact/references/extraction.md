# Extraction and multimodal reading

How to get the raw material out of a video and read it well. `scripts/extract.py` does the mechanical
part; this file covers choosing its options, reading its output, and what to do when a tool fails.

---

## 1. Running the extractor

```bash
python scripts/extract.py "<URL>" --out "<work dir>"          # auto frame interval
python scripts/extract.py "<URL>" --frames scene --out ...     # UI demos, slide decks
python scripts/extract.py "<URL>" --frames none --out ...      # transcript only (fast)
python scripts/extract.py "<URL>" --start 600 --end 1500 ...   # frames for one section only
```

Paths are relative to the skill folder; resolve them to wherever this skill is installed. Use a
temporary directory for `--out` (the OS temp dir, or a git-ignored folder), never the user's source tree.

It prints a JSON manifest to stdout and progress to stderr. Read the manifest's `degraded` list before
anything else: it is the list of things you must tell the user about.

What each tool buys you, and what happens without it:

| Tool | Used for | Without it |
|---|---|---|
| `youtube-transcript-api` (pip) | transcript, tried first | falls back to yt-dlp caption tracks |
| `yt-dlp` (pip or standalone) | metadata, caption tracks, video download | title/channel via YouTube oEmbed; transcript only if the API works; no frames |
| `ffmpeg` + `ffprobe` | frame extraction | no frames: transcript-only analysis |

If NEITHER transcript source nor frames work, the extractor exits 2. Stop and tell the user which tools
to install (`pip install yt-dlp youtube-transcript-api`, plus ffmpeg from the OS package manager or
ffmpeg.org). Do not attempt to "analyse" a video from its title.

## 2. Frame strategy

`--frames auto` picks the interval from the duration and caps the count (`--max-frames`, default 120):

| Duration | Interval | Why |
|---|---|---|
| under 5 min | 10s | dense coverage is cheap |
| 5-20 min | 20s | coverage vs volume |
| 20-60 min | 40s | key moments; lean on the transcript to find the rest |
| over 60 min | 60s | agree a focus with the user first (whole video, or chapters/sections) |

Use `--frames scene` for software demos, screen recordings and slide talks: it keeps a frame each
time the picture changes substantially, so every new slide or screen is captured and static stretches
cost nothing. Talking-head videos do not need scene mode; the frames add little beyond confirming
there are no visuals, so a coarse interval is enough.

Frames are real source frames with exact timestamps in `frames.json` (`t` in seconds, `ts` as text).

## 3. Reading order

1. **Transcript first, end to end.** Build a topic outline with timestamps. Mark "look here" moments:
   "as you can see", "on the screen", "this diagram", "let me show you", "here's the code", slide
   transitions ("next", "so moving on").
2. **Frames in batches of 8-10**, in order, so you can see what changed between them. For each,
   note: on-screen text (code, labels, URLs, errors, slide titles), diagrams and charts, UI state
   (menus, dialogs, settings), and what changed since the previous frame.
3. **Targeted re-extraction** when a "look here" moment fell between two frames: rerun with
   `--start/--end` around it and a small fixed interval (e.g. `--frames 2`) into a separate `--out`.

## 4. Fusing the two channels

For each key moment, write down both channels and the synthesis:

```
[12:40]
  SAID:   "then you just flip this setting on"
  SHOWN:  Settings > Advanced, toggle labelled "Strict mode", currently off
  MEANS:  Enable Settings > Advanced > "Strict mode"
```

Flag **visual-only information** explicitly: menu paths, exact button labels, code that was shown but
not read aloud, error messages, numbers on charts, before/after states. This is usually the most
valuable thing the artifact adds over the transcript, and it is what a text-only summary misses.

## 5. Troubleshooting

| Symptom | Cause | Do this |
|---|---|---|
| `youtube-transcript-api failed: ParseError` or `...Blocked` | old library version, or YouTube blocking the IP | nothing, if the yt-dlp fallback worked; otherwise `pip install -U youtube-transcript-api` |
| caption fetch returns an HTML page | rate limit (HTTP 429) | the script retries twice with a 10s wait; if it still fails, wait a few minutes |
| `HTTP Error 403: Forbidden` on download | yt-dlp is out of date for YouTube's current player, or the video needs a signed-in session | update yt-dlp (`pip install -U yt-dlp`, or `yt-dlp -U` for the standalone binary); retry with `--cookies-from-browser firefox` (or chrome, edge...); otherwise continue transcript-only and say so |
| age-restricted / members-only / private | needs an account | `--cookies-from-browser`, only if the user agrees; never ask for passwords |
| no captions at all | the uploader disabled them and there are no auto-captions | frames-only analysis; say prominently that nothing was heard, only seen |
| captions only in another language | the script falls back to the original-language track | analyse in that language, write the artifact in the user's language, keep quotes in the original with a translation beside them |
| transcript has odd word breaks or the wrong language label | the uploader set the wrong video language, so YouTube's speech recognition ran in that language | the script restores spaces between Latin words; quality is still lower, so treat quotes cautiously and check them against frames |
| video is a live stream still running | nothing stable to extract | tell the user to come back after it ends |

Updating the user's tools changes their environment: ask before running an install or upgrade.
