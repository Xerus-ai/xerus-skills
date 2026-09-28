#!/usr/bin/env python3
"""Extract metadata, a timestamped transcript and frames from a YouTube video.

Stdlib only. Optional tools are feature-detected, each with a fallback:
  - yt-dlp                  metadata, caption URLs, video download
  - youtube-transcript-api  transcript (tried first; any 0.6+ version)
  - ffmpeg / ffprobe        frame extraction

Usage:
  python extract.py URL [--out DIR] [--frames auto|scene|none|SECONDS]
                        [--max-frames N] [--lang en,de] [--start S] [--end S]
                        [--cookies-from-browser BROWSER]

Writes into DIR (default: a fresh temp dir, printed at the end):
  metadata.json    title, channel, duration, id, upload date, description, chapters
  transcript.txt   one "[mm:ss] text" line per caption segment
  transcript.json  [{"start": s, "end": s, "text": ...}, ...]
  frames/          frame_0001.jpg ...
  frames.json      [{"file": "frames/frame_0001.jpg", "t": seconds}, ...]
  manifest.json    what succeeded, what degraded and why

Exit code: 0 if a transcript or frames were produced, 2 if neither, 1 on bad input.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def log(msg):
    print(f"[extract] {msg}", file=sys.stderr, flush=True)


def video_id_from_url(url):
    p = urllib.parse.urlparse(url)
    host = (p.hostname or "").lower()
    if host.endswith("youtu.be"):
        return p.path.lstrip("/").split("/")[0] or None
    if "youtube" in host:
        q = urllib.parse.parse_qs(p.query)
        if "v" in q:
            return q["v"][0]
        m = re.match(r"^/(shorts|embed|live|v)/([^/?#]+)", p.path)
        if m:
            return m.group(2)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    return None


def fmt_ts(seconds):
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def yt_dlp_cmd():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return None


def http_get(url, retries=2):
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
            if body.lstrip().startswith("<"):
                raise ValueError("got an HTML page instead of data (likely rate-limited)")
            return body
        except Exception as e:  # noqa: BLE001 - report and retry any network failure
            if attempt == retries:
                raise
            log(f"fetch failed ({e}); retrying in 10s")
            time.sleep(10)


# ---------------------------------------------------------------- metadata

def get_metadata(url, vid, ytdlp):
    if ytdlp:
        try:
            out = subprocess.run(ytdlp + ["--dump-json", "--skip-download", "--no-warnings", url],
                                 capture_output=True, text=True, encoding="utf-8", timeout=180)
            if out.returncode == 0 and out.stdout.strip():
                return json.loads(out.stdout.splitlines()[0]), None
            err = (out.stderr or "").strip().splitlines()
            reason = err[-1] if err else f"exit {out.returncode}"
        except Exception as e:  # noqa: BLE001
            reason = str(e)
        log(f"yt-dlp metadata failed: {reason}")
    else:
        reason = "yt-dlp not installed"
    # Fallback: oEmbed gives title + channel, but no duration/description/captions.
    try:
        q = urllib.parse.urlencode({"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
        o = json.loads(http_get(f"https://www.youtube.com/oembed?{q}", retries=0))
        return {"id": vid, "title": o.get("title"), "channel": o.get("author_name")}, \
            f"partial metadata via oEmbed ({reason})"
    except Exception as e:  # noqa: BLE001
        return {"id": vid}, f"no metadata ({reason}; oEmbed: {e})"


def trim_metadata(info, url):
    keep = ["id", "title", "channel", "uploader", "upload_date", "duration", "description",
            "chapters", "tags", "webpage_url"]
    m = {k: info.get(k) for k in keep if info.get(k) is not None}
    m.setdefault("webpage_url", url)
    if "channel" not in m and "uploader" in m:
        m["channel"] = m["uploader"]
    if m.get("chapters"):
        m["chapters"] = [{"start": c.get("start_time"), "end": c.get("end_time"), "title": c.get("title")}
                         for c in m["chapters"]]
    return m


# ---------------------------------------------------------------- transcript

def transcript_via_api(vid, langs):
    try:
        import youtube_transcript_api as yta
    except ImportError:
        return None, "youtube-transcript-api not installed"
    api = yta.YouTubeTranscriptApi
    try:
        if hasattr(api, "get_transcript"):  # 0.6.x: class methods, list of dicts
            try:
                raw = api.get_transcript(vid, languages=langs)
            except Exception:  # noqa: BLE001 - preferred languages missing; take any
                raw = next(iter(api.list_transcripts(vid))).fetch()
            rows = [(d["start"], d.get("duration", 0), d["text"]) for d in raw]
        else:  # 1.x: instance methods, snippet objects
            inst = api()
            try:
                fetched = inst.fetch(vid, languages=langs)
            except Exception:  # noqa: BLE001
                fetched = next(iter(inst.list(vid))).fetch()
            rows = [(s.start, s.duration, s.text) for s in fetched]
    except Exception as e:  # noqa: BLE001
        return None, f"youtube-transcript-api failed: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}"
    return [{"start": round(s, 2), "end": round(s + d, 2), "text": t.replace("\n", " ").strip()}
            for s, d, t in rows if t and t.strip()], None


def caption_url_from_info(info, langs):
    """Pick a caption track, preferring the speaker's own words over machine translation."""
    subs, auto = info.get("subtitles") or {}, info.get("automatic_captions") or {}
    spoken = (info.get("language") or "").split("-")[0]

    def json3(source, lang):
        for f in source.get(lang, []):
            if f.get("ext") == "json3":
                return f["url"]
        return None

    def native_auto(lang):  # auto track in the video's own language, not a translation
        if auto.get(lang + "-orig"):
            return lang + "-orig"
        return lang if lang == spoken else None

    order = [(subs, l, False) for l in langs]                                        # 1. manual, preferred
    order += [(auto, native_auto(l), True) for l in langs if native_auto(l)]         # 2. native auto, preferred
    order += [(auto, l, True) for l in auto if l.endswith("-orig")]                  # 3. native auto, any
    if spoken:
        order.append((auto, spoken, True))
    order += [(subs, l, False) for l in subs]                                        # 4. manual, any language
    order += [(auto, l, True) for l in langs]                                        # 5. translated (rate-limited, last)
    for source, lang, is_auto in order:
        url = json3(source, lang)
        if url:
            if lang not in langs or source is subs:
                url = re.sub(r"&tlang=[^&]+", "", url)
            return url, lang, is_auto
    return None, None, None


def join_tokens(tokens):
    """Join caption tokens. A track mislabelled as a no-space language (e.g. English speech tagged
    Japanese) arrives as bare Latin words; put the missing spaces back without touching CJK text."""
    out = ""
    for t in tokens:
        if out and t and out[-1].isascii() and out[-1].isalnum() and t[0].isascii() and t[0].isalnum():
            out += " "
        out += t
    return out


def transcript_via_ytdlp(info, langs):
    if not info or not (info.get("subtitles") or info.get("automatic_captions")):
        return None, "no caption tracks in yt-dlp metadata"
    url, lang, is_auto = caption_url_from_info(info, langs)
    if not url:
        return None, "no json3 caption track found"
    try:
        data = json.loads(http_get(url))
    except Exception as e:  # noqa: BLE001
        return None, f"caption download failed: {e}"
    segs = []
    for ev in data.get("events", []):
        text = join_tokens(s.get("utf8", "") for s in ev.get("segs") or []).replace("\n", " ").strip()
        if not text:
            continue
        start = ev.get("tStartMs", 0) / 1000
        segs.append({"start": round(start, 2), "end": round(start + ev.get("dDurationMs", 0) / 1000, 2),
                     "text": text})
    log(f"captions via yt-dlp ({lang}, {'auto' if is_auto else 'manual'})")
    return segs or None, None if segs else "caption track was empty"


# ---------------------------------------------------------------- frames

def auto_interval(duration):
    if duration is None:
        return 30
    if duration < 5 * 60:
        return 10
    if duration < 20 * 60:
        return 20
    if duration < 60 * 60:
        return 40
    return 60


def download_video(url, work, ytdlp):
    # Video-only stream at <=720p: frames need no audio, and skipping it avoids a merge step.
    fmt = "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]/bv*/b"
    out = subprocess.run(ytdlp + ["-f", fmt, "--no-playlist", "--no-warnings", "-o",
                                  os.path.join(work, "video.%(ext)s"), url],
                         capture_output=True, text=True, encoding="utf-8", timeout=1800)
    files = [f for f in glob.glob(os.path.join(work, "video.*")) if not f.endswith(".part")]
    if out.returncode != 0 or not files:
        err = (out.stderr or "").strip().splitlines()
        return None, err[-1] if err else f"yt-dlp exit {out.returncode}"
    return files[0], None


def probe_duration(video):
    if not shutil.which("ffprobe"):
        return None
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def extract_frames(video, work, mode, duration, max_frames, start, end):
    fdir = os.path.join(work, "frames")
    shutil.rmtree(fdir, ignore_errors=True)  # never mix in frames from an earlier run
    os.makedirs(fdir)
    span_start = start or 0
    span = (end or duration or 0) - span_start
    trim = []
    if start:
        trim += ["-ss", str(start)]
    if end:
        trim += ["-to", str(end)]
    scale = "scale='min(1280,iw)':-2"
    if mode == "scene":
        interval = None
        pick = "eq(n,0)+gt(scene,0.3)"  # always keep the opening frame (its scene score is NaN)
    else:
        interval = float(mode) if mode != "auto" else auto_interval(span or duration)
        if span and span / interval > max_frames:
            interval = span / max_frames
            log(f"widened frame interval to {interval:.1f}s to stay under {max_frames} frames")
        # select (not fps) so each kept frame is a real source frame with an exact timestamp
        pick = f"isnan(prev_selected_t)+gte(t-prev_selected_t,{interval})"
    cmd = ["ffmpeg", "-hide_banner", "-y", *trim, "-i", video, "-vf", f"select='{pick}',{scale},showinfo",
           "-vsync", "vfr", "-frames:v", str(max_frames), "-q:v", "3", os.path.join(fdir, "frame_%04d.jpg")]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    times = [float(t) + span_start for t in re.findall(r"pts_time:([0-9.]+)", out.stderr)]
    files = sorted(glob.glob(os.path.join(fdir, "frame_*.jpg")))
    if out.returncode != 0 or not files:
        if out.returncode == 0 or "Nothing was written" in out.stderr:
            if mode == "scene":
                return None, None, "scene mode found no picture changes; rerun with --frames auto"
            return None, None, "ffmpeg selected no frames; try a smaller interval or check --start/--end"
        err = [l for l in out.stderr.strip().splitlines() if l.strip()]
        return None, None, err[-1] if err else f"ffmpeg exit {out.returncode}"
    rows = []
    for i, f in enumerate(files):
        t = times[i] if i < len(times) else None
        rows.append({"file": "frames/" + os.path.basename(f), "t": round(t, 1) if t is not None else None,
                     "ts": fmt_ts(t) if t is not None else None})
    return rows, interval, None


# ---------------------------------------------------------------- main

def main():
    for stream in (sys.stdout, sys.stderr):  # titles/quotes may not fit a legacy console codepage
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", help="working directory (default: new temp dir)")
    ap.add_argument("--frames", default="auto", help="auto | scene | none | fixed interval in seconds")
    ap.add_argument("--max-frames", type=int, default=120)
    ap.add_argument("--lang", default="en", help="preferred caption languages, comma-separated")
    ap.add_argument("--start", type=float, help="only frames from this second")
    ap.add_argument("--end", type=float, help="only frames up to this second")
    ap.add_argument("--cookies-from-browser", metavar="BROWSER",
                    help="passed to yt-dlp (e.g. firefox) for age-gated videos or 403 errors")
    a = ap.parse_args()

    vid = video_id_from_url(a.url)
    if not vid:
        log(f"not a recognisable YouTube URL: {a.url}")
        return 1
    if a.frames not in ("auto", "scene", "none"):
        try:
            if float(a.frames) <= 0:
                raise ValueError
        except ValueError:
            log("--frames must be auto, scene, none, or a positive number of seconds")
            return 1
    url = f"https://www.youtube.com/watch?v={vid}"
    work = os.path.abspath(a.out) if a.out else tempfile.mkdtemp(prefix="yt-artifact-")
    os.makedirs(work, exist_ok=True)
    langs = [l.strip() for l in a.lang.split(",") if l.strip()]

    ytdlp = yt_dlp_cmd()
    if ytdlp and a.cookies_from_browser:
        ytdlp += ["--cookies-from-browser", a.cookies_from_browser]
    tools = {"yt-dlp": bool(ytdlp), "ffmpeg": bool(shutil.which("ffmpeg")),
             "ffprobe": bool(shutil.which("ffprobe"))}
    try:
        import youtube_transcript_api  # noqa: F401
        tools["youtube-transcript-api"] = True
    except ImportError:
        tools["youtube-transcript-api"] = False
    log("tools: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in tools.items()))
    degraded = []

    info, note = get_metadata(url, vid, ytdlp)
    if note:
        degraded.append(note)
    meta = trim_metadata(info, url)
    with open(os.path.join(work, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    log(f"metadata: {meta.get('title')!r} by {meta.get('channel')!r}, "
        f"{fmt_ts(meta['duration']) if meta.get('duration') else 'unknown duration'}")

    segs, why_api = transcript_via_api(vid, langs)
    transcript_source = "youtube-transcript-api" if segs else None
    if not segs:
        log(f"transcript API path unavailable: {why_api}; trying yt-dlp captions")
        segs, why_dlp = transcript_via_ytdlp(info if ytdlp else None, langs)
        transcript_source = "yt-dlp captions" if segs else None
        if not segs:
            degraded.append(f"no transcript ({why_api}; {why_dlp})")
    if segs:
        with open(os.path.join(work, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(segs, f, ensure_ascii=False, indent=1)
        with open(os.path.join(work, "transcript.txt"), "w", encoding="utf-8") as f:
            f.writelines(f"[{fmt_ts(s['start'])}] {s['text']}\n" for s in segs)
        log(f"transcript: {len(segs)} segments via {transcript_source}")

    frames, interval = None, None
    if a.frames == "none":
        degraded.append("frames skipped (--frames none)")
    elif not ytdlp or not tools["ffmpeg"]:
        missing = [n for n, ok in (("yt-dlp", ytdlp), ("ffmpeg", tools["ffmpeg"])) if not ok]
        degraded.append(f"no frames ({' and '.join(missing)} not installed): transcript-only analysis")
    else:
        log("downloading video (<=720p, video only)")
        video, err = download_video(url, work, ytdlp)
        if not video:
            degraded.append(f"no frames (download failed: {err})")
        else:
            duration = probe_duration(video) or meta.get("duration")
            frames, interval, err = extract_frames(video, work, a.frames, duration, a.max_frames,
                                                   a.start, a.end)
            if frames:
                with open(os.path.join(work, "frames.json"), "w", encoding="utf-8") as f:
                    json.dump(frames, f, indent=1)
                log(f"frames: {len(frames)} ({'scene-change' if a.frames == 'scene' else f'every {interval:g}s'})")
                if a.frames == "scene" and len(frames) == 1 and (duration or 0) > 30:
                    degraded.append("scene mode found no picture changes after the first frame; "
                                    "rerun with --frames auto")
            else:
                degraded.append(f"no frames ({err})")
            os.remove(video)  # frames are what we need; the video is large

    manifest = {
        "url": url, "work_dir": work, "tools": tools,
        "title": meta.get("title"), "channel": meta.get("channel"), "duration": meta.get("duration"),
        "transcript": {"source": transcript_source, "segments": len(segs)} if segs else None,
        "frames": {"count": len(frames), "mode": a.frames, "interval": interval} if frames else None,
        "degraded": degraded,
    }
    with open(os.path.join(work, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if (segs or frames) else 2


if __name__ == "__main__":
    sys.exit(main())
