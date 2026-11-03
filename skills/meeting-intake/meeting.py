# -*- coding: utf-8 -*-
"""Prepare a meeting recording so the whole of it can actually be read.

    python meeting.py <video-or-audio> [--transcript FILE] [--out DIR]
                      [--every 90] [--transcribe] [--model tiny]

It does the mechanical part and nothing else:

  1. measures the recording, so there is a known length to cover
  2. checks a supplied transcript against that length and reports every gap
  3. pulls frames across the whole recording, because what is on the screen
     is usually never said out loud
  4. transcribes the audio when asked, with timestamps

It makes no judgement about the meeting. Reading the frames and the words,
and working out what was decided, is the job the skill beside this describes.

Needs ffmpeg and ffprobe. --transcribe also needs whisper.
"""
import io, json, os, re, subprocess, sys

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
STAMP = re.compile(r"(?<!\d)(\d{1,2}):([0-5]\d)(?::([0-5]\d))?(?!\d)")


def run(cmd, timeout=1800):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def need(tool):
    from shutil import which
    if not which(tool):
        print("%s is not installed, and this cannot run without it." % tool)
        sys.exit(2)


def probe(path):
    need("ffprobe")
    p = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size", "-show_entries",
             "stream=codec_type,codec_name,width,height",
             "-of", "json", path], timeout=120)
    try:
        d = json.loads(p.stdout)
    except Exception:
        print("ffprobe could not read %s" % path)
        sys.exit(2)
    dur = float((d.get("format") or {}).get("duration") or 0)
    streams = d.get("streams") or []
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    vid = next((s for s in streams if s.get("codec_type") == "video"), None)
    return {
        "duration": dur,
        "size_mb": int((d.get("format") or {}).get("size") or 0) / 1048576.0,
        "has_audio": has_audio,
        "width": (vid or {}).get("width"),
        "height": (vid or {}).get("height"),
    }


def transcript_marks(text):
    """Every timestamp in the transcript, in seconds, in order."""
    out = []
    for h, m, s in STAMP.findall(text):
        if s:                       # H:MM:SS
            out.append(int(h) * 3600 + int(m) * 60 + int(s))
        else:                       # MM:SS
            out.append(int(h) * 60 + int(m))
    return sorted(out)


def coverage(marks, duration, gap_limit=180):
    """Where the transcript goes quiet for longer than it plausibly should."""
    issues = []
    if not marks:
        return ["The transcript carries no timestamps, so there is no way to "
                "tell which part of the recording it covers. Treat it as "
                "unverified."]
    if marks[0] > gap_limit:
        issues.append("starts at %s - the first %s is not in it"
                      % (hms(marks[0]), hms(marks[0])))
    for a, b in zip(marks, marks[1:]):
        if b - a > gap_limit:
            issues.append("silent from %s to %s (%s)"
                          % (hms(a), hms(b), hms(b - a)))
    tail = duration - marks[-1]
    if tail > gap_limit:
        issues.append("ends at %s but the recording runs to %s - the last %s "
                      "is not in it" % (hms(marks[-1]), hms(duration), hms(tail)))
    return issues


def hms(s):
    s = int(s)
    return ("%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)) if s >= 3600 \
        else ("%d:%02d" % (s // 60, s % 60))


def frames(path, out_dir, every, duration):
    need("ffmpeg")
    fdir = os.path.join(out_dir, "frames")
    os.makedirs(fdir, exist_ok=True)
    for f in os.listdir(fdir):
        if f.startswith("f_"):
            os.remove(os.path.join(fdir, f))
    run(["ffmpeg", "-nostdin", "-v", "error", "-i", path,
         "-vf", "fps=1/%d,scale=1280:-2" % every, "-q:v", "4",
         os.path.join(fdir, "f_%03d.jpg")], timeout=1800)
    got = sorted(f for f in os.listdir(fdir) if f.startswith("f_"))
    index = []
    for i, f in enumerate(got):
        index.append({"file": f, "at": hms(i * every), "seconds": i * every})

    # The interval filter stops at the last whole interval, so a recording of
    # 26:49 sampled every 2 minutes ends at 24:00 and the last 2:49 is never
    # seen. A meeting's decisions are usually at the end, so take one more
    # frame just before it stops.
    tail = duration - (index[-1]["seconds"] if index else 0)
    if tail > 2:
        last = "f_zz_end.jpg"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y",
             "-ss", "%.2f" % max(0, duration - 2), "-i", path,
             "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "4",
             os.path.join(fdir, last)], timeout=300)
        if os.path.isfile(os.path.join(fdir, last)):
            index.append({"file": last, "at": hms(duration - 2),
                          "seconds": int(duration - 2)})
    io.open(os.path.join(fdir, "index.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(index, indent=1) + "\n")
    return fdir, index


def transcribe(path, out_dir, model):
    need("whisper")
    wav = os.path.join(out_dir, "audio.wav")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", path,
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], timeout=1800)
    print("transcribing with whisper %s. Roughly 0.6x real time on this "
          "machine with tiny, slower with a larger model." % model)
    p = run(["whisper", wav, "--model", model, "--language", "en",
             "--output_format", "txt", "--output_dir", out_dir,
             "--fp16", "False"], timeout=10800)
    if p.returncode != 0:
        print("whisper failed:\n%s" % (p.stderr or p.stdout)[-800:])
        return None
    made = os.path.join(out_dir, "audio.txt")
    return made if os.path.isfile(made) else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    def flag(name, default=None):
        return sys.argv[sys.argv.index("--" + name) + 1] \
            if "--" + name in sys.argv and \
            sys.argv.index("--" + name) + 1 < len(sys.argv) else default
    if not args:
        print(__doc__)
        return 2
    media = args[0]
    if not os.path.isfile(media):
        print("no such file: %s" % media)
        return 2
    out_dir = os.path.abspath(flag("out") or
                              os.path.join(os.path.dirname(media) or ".",
                                           "meeting-" + os.path.splitext(
                                               os.path.basename(media))[0]))
    os.makedirs(out_dir, exist_ok=True)
    every = int(flag("every", "90"))
    tpath = flag("transcript")

    info = probe(media)
    print("# Meeting intake\n")
    print("recording : %s" % media)
    print("length    : %s (%.0f MB)" % (hms(info["duration"]), info["size_mb"]))
    if info["width"]:
        print("video     : %dx%d" % (info["width"], info["height"]))
    print("audio     : %s" % ("yes" if info["has_audio"] else "NO AUDIO TRACK"))
    print("workspace : %s\n" % out_dir)

    # --- the transcript -------------------------------------------------
    tfile = None
    if tpath and os.path.isfile(tpath):
        tfile = tpath
        text = io.open(tpath, encoding="utf-8", errors="replace").read()
        marks = transcript_marks(text)
        print("## Supplied transcript\n")
        print("file       : %s" % tpath)
        print("words      : %d" % len(text.split()))
        print("timestamps : %d" % len(marks))
        gaps = coverage(marks, info["duration"])
        if gaps:
            print("\n**This transcript does not cover the whole recording.**")
            for g in gaps:
                print("  - %s" % g)
            print("\nRead those stretches off the frames, or transcribe the "
                  "audio with --transcribe, before concluding anything.")
        else:
            print("coverage   : reaches %s of %s, no gap over 3 minutes"
                  % (hms(marks[-1]) if marks else "?", hms(info["duration"])))
        print("")
    elif "--transcribe" in sys.argv:
        if not info["has_audio"]:
            print("## No transcript\n\nThere is no audio track to transcribe.\n")
        else:
            made = transcribe(media, out_dir, flag("model", "tiny"))
            if made:
                tfile = made
                print("\ntranscript written: %s\n" % made)
    else:
        print("## No transcript\n")
        print("None supplied. Either pass one with --transcript, or add "
              "--transcribe to make one from the audio.\n")

    # --- the frames -----------------------------------------------------
    fdir, index = frames(media, out_dir, every, info["duration"])
    print("## Frames\n")
    print("%d frames, one every %ds, covering %s to %s"
          % (len(index), every, index[0]["at"] if index else "-",
             index[-1]["at"] if index else "-"))
    print("folder: %s\n" % fdir)
    print("Open every one of them. What is on a shared screen - a number, a "
          "URL, a layout, a spreadsheet - is almost never read out loud, so "
          "it exists nowhere in the transcript.\n")
    if index:
        print("| frame | at |")
        print("|---|---|")
        for f in index:
            print("| `%s` | %s |" % (f["file"], f["at"]))

    io.open(os.path.join(out_dir, "intake.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(
                {"media": os.path.abspath(media), "info": info,
                 "transcript": os.path.abspath(tfile) if tfile else None,
                 "frames": index, "every": every}, indent=1) + "\n")
    print("\nNext: read the transcript end to end and every frame, then write "
          "the brief. The skill says what the brief has to answer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
