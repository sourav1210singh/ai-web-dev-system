# -*- coding: utf-8 -*-
"""Does the intake report coverage honestly?

The point of this tool is the promise that nothing was skipped, so the part
worth testing is the part that detects a gap. Builds its own tiny video with
ffmpeg, so it needs no sample file.
"""
import importlib.util, io, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def load():
    spec = importlib.util.spec_from_file_location(
        "meetingmod", os.path.join(HERE, "meeting.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    m = load()

    # --- timestamp parsing ----------------------------------------------
    ok("reads MM:SS marks",
       m.transcript_marks("**A** *[00:00]*: hi\n**B** *[02:30]*: yes") == [0, 150])
    ok("reads H:MM:SS marks",
       m.transcript_marks("at 1:02:03 we agreed") == [3723])
    ok("ignores numbers that are not times",
       m.transcript_marks("we need 1200 units and 4500 more") == [])
    ok("sorts what it finds",
       m.transcript_marks("[05:00] then [01:00]") == [60, 300])

    # --- the gap report, which is the whole promise ----------------------
    full = list(range(0, 1200, 60))            # 0 to 19:00, 20 minutes
    ok("a transcript that keeps up reports nothing",
       m.coverage(full, 1205) == [])

    ok("a transcript that stops early is called short",
       any("not in it" in g for g in m.coverage(list(range(0, 600, 60)), 1800)),
       m.coverage(list(range(0, 600, 60)), 1800))

    ok("a late start is reported",
       any("first" in g for g in m.coverage([400, 460, 520], 560)))

    holed = [0, 60, 120, 900, 960]
    gaps = m.coverage(holed, 1000)
    ok("a hole in the middle is reported",
       any("silent from 2:00 to 15:00" in g for g in gaps), gaps)

    ok("no timestamps is reported as unverifiable",
       m.coverage([], 600) and "unverified" in m.coverage([], 600)[0])

    ok("formats times as a person reads them",
       m.hms(59) == "0:59" and m.hms(600) == "10:00" and m.hms(3723) == "1:02:03")

    # --- end to end on a real file ---------------------------------------
    if not shutil.which("ffmpeg"):
        print("\n(ffmpeg not installed, skipping the end-to-end check)")
    else:
        tmp = tempfile.mkdtemp(prefix="meeting_")
        try:
            vid = os.path.join(tmp, "clip.mp4")
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-y",
                 "-f", "lavfi", "-i", "testsrc=size=640x360:rate=10:duration=25",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=25",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                 "-shortest", vid], capture_output=True, timeout=300)
            ok("a test clip was built", os.path.isfile(vid))

            info = m.probe(vid)
            ok("measures the length", 24 <= info["duration"] <= 26,
               "%.1fs" % info["duration"])
            ok("sees the audio track", info["has_audio"])
            ok("reads the frame size", info["width"] == 640)

            out = os.path.join(tmp, "work")
            os.makedirs(out, exist_ok=True)
            fdir, index = m.frames(vid, out, 10, info["duration"])
            ok("pulls frames across the clip", len(index) >= 3, len(index))
            ok("every frame it lists exists",
               all(os.path.isfile(os.path.join(fdir, f["file"])) for f in index))
            ok("the last frame reaches the end of the recording",
               index[-1]["seconds"] >= info["duration"] - 3,
               "last at %ss of %.0fs" % (index[-1]["seconds"], info["duration"]))
            ok("no stretch at the end is left without a frame",
               info["duration"] - index[-1]["seconds"] <= 3,
               "%.0fs uncovered" % (info["duration"] - index[-1]["seconds"]))
            ok("writes an index beside the frames",
               os.path.isfile(os.path.join(fdir, "index.json")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
