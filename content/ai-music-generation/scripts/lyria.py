#!/usr/bin/env python3
"""Render a fixed-length instrumental clip with Google Lyria RealTime to a WAV file.

Lyria RealTime is a streaming model: you open a session, send weighted prompts and a
generation config, press play, and it streams raw 16-bit PCM (48 kHz, stereo) until you
stop it. This script collects that stream, trims it to --duration seconds and writes a
standard WAV with the stdlib `wave` module.

Requires: pip install google-genai   (a version that has client.aio.live.music)
Auth:     GEMINI_API_KEY or GOOGLE_API_KEY (create one at https://aistudio.google.com/apikey)

Examples:
  python lyria.py --prompt "minimal techno" --bpm 124 --duration 30 -o techno.wav
  python lyria.py --prompt "lo-fi hip hop:1.0" --prompt "rhodes piano:0.6" \
      --prompt "rainy, nostalgic:0.4" --bpm 80 --scale F_MAJOR_D_MINOR -d 45 -o study.wav
  python lyria.py --prompt "cinematic orchestral" --dry-run   # validate args, no API call
"""
import argparse
import asyncio
import json
import os
import sys
import wave

SAMPLE_RATE = 48000  # Lyria RealTime output, per Google's docs
CHANNELS = 2
SAMPLE_WIDTH = 2  # bytes -> 16-bit PCM
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH

DEFAULT_MODEL = "models/lyria-realtime-exp"
DEFAULT_API_VERSION = "v1beta"

SCALES = [
    "C_MAJOR_A_MINOR", "D_FLAT_MAJOR_B_FLAT_MINOR", "D_MAJOR_B_MINOR",
    "E_FLAT_MAJOR_C_MINOR", "E_MAJOR_D_FLAT_MINOR", "F_MAJOR_D_MINOR",
    "G_FLAT_MAJOR_E_FLAT_MINOR", "G_MAJOR_E_MINOR", "A_FLAT_MAJOR_F_MINOR",
    "A_MAJOR_G_FLAT_MINOR", "B_FLAT_MAJOR_G_MINOR", "B_MAJOR_A_FLAT_MINOR",
]
MODES = ["QUALITY", "DIVERSITY", "VOCALIZATION"]


def parse_prompt(raw):
    """'text' or 'text:weight' -> (text, weight). Weight defaults to 1.0 and may not be 0."""
    text, weight = raw, 1.0
    if ":" in raw:
        head, tail = raw.rsplit(":", 1)
        try:
            weight = float(tail)
            text = head
        except ValueError:
            pass  # the colon was part of the prompt text
    text = text.strip()
    if not text:
        raise argparse.ArgumentTypeError(f"empty prompt in {raw!r}")
    if weight == 0:
        raise argparse.ArgumentTypeError(f"weight 0 is not allowed ({raw!r})")
    return text, weight


def ranged(lo, hi, cast=float):
    def check(value):
        v = cast(value)
        if not lo <= v <= hi:
            raise argparse.ArgumentTypeError(f"{v} is outside [{lo}, {hi}]")
        return v
    return check


def build_parser():
    p = argparse.ArgumentParser(
        description="Generate an instrumental clip with Google Lyria RealTime and save it as WAV.",
        epilog="Instrumental only. For songs with vocals/lyrics see SKILL.md (Lyria 3.5).",
    )
    p.add_argument("-p", "--prompt", action="append", type=parse_prompt, required=True,
                   metavar="TEXT[:WEIGHT]",
                   help="Weighted prompt; repeat to blend (e.g. -p 'jazz fusion:1.0' -p 'tabla:0.5'). "
                        "Weight defaults to 1.0 and must be non-zero.")
    p.add_argument("-d", "--duration", type=ranged(1, 600), default=30.0,
                   help="Seconds of audio to keep (default 30).")
    p.add_argument("-o", "--output", default="lyria.wav", help="Output .wav path (default lyria.wav).")
    p.add_argument("--bpm", type=ranged(60, 200, int), help="Tempo 60-200 (model decides if omitted).")
    p.add_argument("--scale", choices=SCALES, metavar="SCALE",
                   help="Key/scale (model decides if omitted). One of: " + ", ".join(SCALES))
    p.add_argument("--density", type=ranged(0.0, 1.0), help="Note density 0-1 (sparse to busy).")
    p.add_argument("--brightness", type=ranged(0.0, 1.0), help="Tonal brightness 0-1.")
    p.add_argument("--guidance", type=ranged(0.0, 6.0), help="Prompt adherence 0-6 (API default 4.0).")
    p.add_argument("--temperature", type=ranged(0.0, 3.0), help="Randomness 0-3 (API default 1.1).")
    p.add_argument("--top-k", type=ranged(1, 1000, int), help="Top-k sampling 1-1000 (API default 40).")
    p.add_argument("--seed", type=ranged(0, 2147483647, int), help="Seed for repeatable output.")
    p.add_argument("--mode", choices=MODES, help="QUALITY (API default), DIVERSITY, or VOCALIZATION "
                                                 "(wordless vocal sounds used as an instrument).")
    p.add_argument("--mute-bass", action="store_true")
    p.add_argument("--mute-drums", action="store_true")
    p.add_argument("--only-bass-and-drums", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Model id (default {DEFAULT_MODEL}).")
    p.add_argument("--api-version", default=DEFAULT_API_VERSION,
                   help=f"Gemini API version for the session (default {DEFAULT_API_VERSION}).")
    p.add_argument("--timeout", type=float, default=None,
                   help="Give up after N seconds of wall time (default: duration*3 + 30).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the resolved request as JSON and exit without calling the API.")
    return p


def config_kwargs(args):
    kw = {
        "bpm": args.bpm, "scale": args.scale, "density": args.density,
        "brightness": args.brightness, "guidance": args.guidance,
        "temperature": args.temperature, "top_k": args.top_k, "seed": args.seed,
        "music_generation_mode": args.mode,
        "mute_bass": args.mute_bass or None, "mute_drums": args.mute_drums or None,
        "only_bass_and_drums": args.only_bass_and_drums or None,
    }
    return {k: v for k, v in kw.items() if v is not None}


def write_wav(path, pcm):
    frame = CHANNELS * SAMPLE_WIDTH
    pcm = pcm[: len(pcm) - len(pcm) % frame]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return len(pcm) / BYTES_PER_SECOND


async def generate(args, api_key):
    from google import genai  # lazy: --help and --dry-run work without the SDK
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options={"api_version": args.api_version})
    target = int(args.duration * BYTES_PER_SECOND)
    buf = bytearray()

    kw = config_kwargs(args)
    if "scale" in kw:
        kw["scale"] = types.Scale[kw["scale"]]
    if "music_generation_mode" in kw:
        kw["music_generation_mode"] = types.MusicGenerationMode[kw["music_generation_mode"]]

    async with client.aio.live.music.connect(model=args.model) as session:
        await session.set_weighted_prompts(
            prompts=[types.WeightedPrompt(text=t, weight=w) for t, w in args.prompt])
        await session.set_music_generation_config(config=types.LiveMusicGenerationConfig(**kw))
        await session.play()
        while len(buf) < target:
            got_any = False
            async for message in session.receive():
                got_any = True
                if message.filtered_prompt:
                    fp = message.filtered_prompt
                    print(f"warning: prompt filtered: {fp.text!r} ({fp.filtered_reason})",
                          file=sys.stderr)
                content = message.server_content
                if content and content.audio_chunks:
                    for chunk in content.audio_chunks:
                        if chunk.data:
                            buf.extend(chunk.data)
                    print(f"\r  {min(len(buf), target) / BYTES_PER_SECOND:6.1f}s / "
                          f"{args.duration:.1f}s", end="", file=sys.stderr, flush=True)
                if len(buf) >= target:
                    break
            if not got_any:
                break  # server closed the stream
        print(file=sys.stderr)
        try:
            await session.stop()
        except Exception:
            pass  # connection may already be closed; the audio is in hand
    return bytes(buf[:target])


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.only_bass_and_drums and (args.mute_bass or args.mute_drums):
        print("error: --only-bass-and-drums conflicts with --mute-bass/--mute-drums", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps({
            "model": args.model, "api_version": args.api_version,
            "weighted_prompts": [{"text": t, "weight": w} for t, w in args.prompt],
            "config": config_kwargs(args), "duration_s": args.duration,
            "output": args.output,
            "format": f"WAV PCM16 {SAMPLE_RATE} Hz {CHANNELS}ch",
        }, indent=2))
        return 0

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("error: set GEMINI_API_KEY or GOOGLE_API_KEY (https://aistudio.google.com/apikey)",
              file=sys.stderr)
        return 2
    try:
        import google.genai  # noqa: F401
    except ImportError:
        print("error: google-genai is not installed: pip install -U google-genai", file=sys.stderr)
        return 2

    timeout = args.timeout or args.duration * 3 + 30
    try:
        pcm = asyncio.run(asyncio.wait_for(generate(args, api_key), timeout))
    except asyncio.TimeoutError:
        print(f"error: timed out after {timeout:.0f}s", file=sys.stderr)
        return 1
    except AttributeError as e:
        print(f"error: {e}\nYour google-genai may predate the live music API: "
              "pip install -U google-genai", file=sys.stderr)
        return 1
    if not pcm:
        print("error: no audio received (prompt filtered or session closed early)", file=sys.stderr)
        return 1
    seconds = write_wav(args.output, pcm)
    if seconds + 0.01 < args.duration:
        print(f"warning: stream ended early; wrote {seconds:.1f}s of {args.duration:.1f}s",
              file=sys.stderr)
    print(f"wrote {args.output} ({seconds:.1f}s, {SAMPLE_RATE} Hz stereo 16-bit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
