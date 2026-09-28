#!/usr/bin/env python3
"""Pre-delivery gate for a youtube-to-artifact HTML file. Stdlib only.

Usage:
  python check_artifact.py ARTIFACT.html [--work DIR]

DIR is the extract.py working directory (for transcript.json and manifest.json).
Without it, only the self-containment and structure checks run.

Checks (each failure is printed; exit 1 if any):
  1. Self-contained: no external scripts, stylesheets, fonts, images or CSS url()s.
     Plain <a href> links out are fine.
  2. Structure: exactly one <h1>, at least one link to the source video.
  3. Timestamp links: every YouTube link with t= points at THIS video and a time
     inside its duration.
  4. Quote fidelity: every <blockquote> must appear verbatim in the transcript
     (compared case-, punctuation- and whitespace-insensitively; an ellipsis may
     elide words between fragments). Paraphrases do not go in <blockquote>.
"""
import argparse
import html.parser
import json
import os
import re
import sys
import urllib.parse

YT_HOSTS = ("youtube.com", "youtu.be")
# Scripts written without spaces between words (CJK, Thai, Lao, Myanmar, Khmer): match by characters.
NO_SPACE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff]")


def norm(text):
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


class Scan(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.external, self.links, self.quotes, self.h1 = [], [], [], 0
        self._quote_depth, self._quote_buf, self._in_style, self.css = 0, [], False, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        remote = lambda v: bool(v) and re.match(r"^(https?:)?//", v.strip(), re.I)  # noqa: E731
        if tag == "script" and remote(a.get("src")):
            self.external.append(f"<script src={a['src']}>")
        if tag == "link" and remote(a.get("href")) and "preconnect" not in (a.get("rel") or ""):
            self.external.append(f"<link href={a['href']}>")
        for attr in ("src", "poster", "data"):
            if tag != "script" and remote(a.get(attr)):
                self.external.append(f"<{tag} {attr}={a[attr]}>")
        for cand in (a.get("srcset") or "").split(","):
            if remote(cand):
                self.external.append(f"<{tag} srcset={cand.strip()}>")
        if tag in ("image", "use", "feimage") and (remote(a.get("href")) or remote(a.get("xlink:href"))):
            self.external.append(f"<{tag} href={a.get('href') or a.get('xlink:href')}>")
        if a.get("style"):
            self.css.append(a["style"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "h1":
            self.h1 += 1
        if tag == "style":
            self._in_style = True
        if tag == "blockquote":
            self._quote_depth += 1

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False
        if tag == "blockquote" and self._quote_depth:
            self._quote_depth -= 1
            if not self._quote_depth:
                self.quotes.append(" ".join("".join(self._quote_buf).split()))
                self._quote_buf = []

    def handle_data(self, data):
        if self._in_style:
            self.css.append(data)
        if self._quote_depth:
            self._quote_buf.append(data)


def yt_link(href):
    p = urllib.parse.urlparse(href)
    host = (p.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in YT_HOSTS):
        return None
    q = urllib.parse.parse_qs(p.query)
    vid = p.path.lstrip("/") if host.endswith("youtu.be") else (q.get("v") or [None])[0]
    t = (q.get("t") or q.get("start") or [None])[0]
    if t is None and p.fragment.startswith("t="):
        t = p.fragment[2:]
    return vid, t


def seconds(t):
    if t is None:
        return None
    if re.fullmatch(r"\d+s?", t):
        return int(t.rstrip("s"))
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", t)
    if m and any(m.groups()):
        h, mi, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + s
    return -1


def main():
    for stream in (sys.stdout, sys.stderr):  # titles/quotes may not fit a legacy console codepage
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("artifact")
    ap.add_argument("--work", help="extract.py working directory")
    a = ap.parse_args()

    with open(a.artifact, encoding="utf-8") as f:
        doc = f.read()
    scan = Scan()
    scan.feed(doc)
    fails, notes = [], []

    for e in scan.external:
        fails.append(f"external resource (breaks offline use): {e}")
    for css in scan.css:
        for u in re.findall(r"(?:url\(|@import\s+)['\"]?((?:https?:)?//[^'\")\s]+)", css, re.I):
            fails.append(f"external CSS resource: {u}")

    if scan.h1 != 1:
        fails.append(f"expected exactly one <h1>, found {scan.h1}")

    manifest, transcript = {}, None
    if a.work:
        mp, tp = os.path.join(a.work, "manifest.json"), os.path.join(a.work, "transcript.json")
        if os.path.exists(mp):
            with open(mp, encoding="utf-8") as f:
                manifest = json.load(f)
        if os.path.exists(tp):
            with open(tp, encoding="utf-8") as f:
                transcript = " " + norm(" ".join(s["text"] for s in json.load(f))) + " "
                transcript_ns = transcript.replace(" ", "")

    vid = yt_link(manifest["url"])[0] if manifest.get("url") else None
    duration = manifest.get("duration")
    yt = [(h, yt_link(h)) for h in scan.links]
    yt = [(h, r) for h, r in yt if r]
    if not yt:
        fails.append("no link back to the source video")
    for href, (lvid, t) in yt:
        if vid and lvid != vid:
            notes.append(f"YouTube link to a different video (fine if intentional): {href}")
        s = seconds(t)
        if s == -1:
            fails.append(f"unparseable timestamp in {href}")
        elif s is not None and duration and s > duration:
            fails.append(f"timestamp past the end of the video ({s}s > {duration}s): {href}")

    if scan.quotes and transcript is None:
        notes.append(f"{len(scan.quotes)} quotes NOT verified (no transcript.json; pass --work)")
    verified = 0
    if transcript is not None:
        for q in scan.quotes:
            # An ellipsis may elide words; each fragment must still appear, in order, as whole words.
            if (len(norm(q).replace(" ", "")) < 6) if NO_SPACE.search(q) else (len(norm(q).split()) < 3):
                fails.append(f"quote too short to verify (need 3+ words, or 6+ characters in CJK/Thai; else drop the blockquote): \"{q}\"")
                continue
            pos = pos_ns = 0
            for frag in (norm(p) for p in re.split(r"\u2026|\.\.\.", q)):
                if not frag:
                    continue
                if NO_SPACE.search(frag):
                    frag = frag.replace(" ", "")
                    i = transcript_ns.find(frag, pos_ns)
                else:
                    i = transcript.find(f" {frag} ", pos)
                if i < 0:
                    fails.append(f"quote not found verbatim in transcript: \"{q[:90]}\"")
                    break
                if NO_SPACE.search(frag):
                    pos_ns = i + len(frag)
                else:
                    pos = i + len(frag) + 1
            else:
                verified += 1

    size = len(doc.encode("utf-8"))
    if size > 3_000_000:
        notes.append(f"artifact is {size / 1e6:.1f} MB; embed fewer or smaller frames")

    for n in notes:
        print(f"NOTE  {n}")
    for f_ in fails:
        print(f"FAIL  {f_}")
    print(f"{'FAIL' if fails else 'PASS'}: {len(fails)} problem(s); {len(yt)} video links "
          f"({sum(1 for _, r in yt if r[1] is not None)} timestamped), "
          f"{verified}/{len(scan.quotes)} quotes verified, {size / 1024:.0f} KB")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
