#!/usr/bin/env python3
"""Turn a WebVTT / SRT subtitle file into clean, de-duplicated transcript text.

Auto-generated YouTube captions repeat each line as it scrolls ("rolling"
captions), carry inline timing tags, and split sentences across cues. This
strips cue numbers, timestamps, tags and the rolling duplicates, and emits
paragraphs with a [mm:ss] marker roughly every 60 seconds so lessons can cite
where an idea came from.

Usage:
    python vtt_to_text.py <subtitles.vtt|.srt> [--out transcript.md]

Python 3 stdlib only.
"""
import html
import re
import sys

TIME_RE = re.compile(r"(\d{1,2}:)?(\d{2}):(\d{2})[.,]\d{3}\s+-->")


def seconds(match):
    h = int(match.group(1)[:-1]) if match.group(1) else 0
    return h * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def clean(line):
    line = re.sub(r"<[^>]+>", "", line)  # <00:00:01.234><c> timing / styling tags
    line = html.unescape(line).replace("​", "")
    return re.sub(r"\s+", " ", line).strip()


def convert(text, marker_every=60):
    words, out, start, last_marker, prev_lines = [], [], None, -marker_every, []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [l for l in block.split("\n") if l.strip()]
        stamp = next((TIME_RE.search(l) for l in lines if TIME_RE.search(l)), None)
        if not stamp:
            continue  # header, NOTE or STYLE block
        t = seconds(stamp)
        body = [clean(l) for l in lines if not TIME_RE.search(l) and not l.strip().isdigit()]
        body = [b for b in body if b]
        # Rolling captions repeat the previous cue's lines; keep only the new ones.
        new = [b for b in body if b not in prev_lines]
        prev_lines = body
        if not new:
            continue
        if t - last_marker >= marker_every and words:
            out.append("[%02d:%02d] %s" % (start // 60, start % 60, " ".join(words)))
            words = []
        if not words:
            start, last_marker = t, t
        words.extend(new)
    if words:
        out.append("[%02d:%02d] %s" % (start // 60, start % 60, " ".join(words)))
    return "\n\n".join(out) + "\n"


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    with open(args[0], encoding="utf-8-sig") as fh:
        result = convert(fh.read())
    if "--out" in args:
        with open(args[args.index("--out") + 1], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(result)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
