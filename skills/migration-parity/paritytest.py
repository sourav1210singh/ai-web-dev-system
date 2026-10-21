# -*- coding: utf-8 -*-
"""Does parity.py report exactly what is missing, and nothing else?

Runs against local fixture files, so it needs no network and cannot be
confused by a live site changing underneath it.
"""
import io, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
RESULTS = []

FILLER = ("Our team has looked after vehicles in this town for nineteen "
          "years and every repair is carried out by a qualified technician "
          "using parts that match the manufacturer specification exactly.")

OLD = """<!doctype html><html><head>
<title>Brake Repair and Servicing</title>
<meta name="description" content="Brake repair, pads, discs and diagnostics.">
<script type="application/ld+json">{"@type":"AutoRepair"}</script>
</head><body>
<h1>Brake Repair and Servicing</h1>
<h2>What is included</h2>
<p>%s</p>
<p>Every brake inspection covers the pads, the discs, the fluid condition
and the handbrake travel, and you get the measurements in writing.</p>
<ul><li>Pad and disc replacement on the same day in most cases</li>
<li>Free brake fluid check with any service booked before noon</li></ul>
<h2>Contact the workshop</h2>
<p>Call us on +1 (555) 123-4567 or write to bookings@example-old.test and we
will come back to you the same working day.</p>
<img src="/img/bay.jpg" alt="A technician measuring brake disc thickness">
<img src="/img/van.jpg" alt="The courtesy van outside the workshop">
<form action="/enquiry"><input name="name"><input name="email">
<input name="vehicle"><textarea name="message"></textarea></form>
<a href="/servicing">Full servicing</a>
<a href="https://maps.example.test/workshop">Find us on the map</a>
</body></html>""" % FILLER

# same content, reworded in places, nothing actually lost
SAME = OLD.replace(
    "Every brake inspection covers the pads, the discs, the fluid condition",
    "Every brake inspection covers the pads, the discs, the fluid level"
).replace("+1 (555) 123-4567", "555-123-4567")

# four real losses: a heading, the phone, the email, an image and its alt
LOSSY = """<!doctype html><html><head>
<title>Brake Repair and Servicing</title>
<meta name="description" content="Brake repair, pads, discs and diagnostics.">
</head><body>
<h1>Brake Repair and Servicing</h1>
<h2>What is included</h2>
<p>%s</p>
<p>Every brake inspection covers the pads, the discs, the fluid condition
and the handbrake travel, and you get the measurements in writing.</p>
<ul><li>Pad and disc replacement on the same day in most cases</li>
<li>Free brake fluid check with any service booked before noon</li></ul>
<img src="/img/bay.jpg" alt="A technician measuring brake disc thickness">
<form action="/enquiry"><input name="name"><input name="email">
<textarea name="message"></textarea></form>
<a href="/servicing">Full servicing</a>
</body></html>""" % FILLER

SHELL = ('<!doctype html><html><head><title>App</title></head>'
         '<body><div id="root"></div></body></html>')


# A big shared nav and footer with a small main area. Whole-page coverage
# stays above 90% even when half the real content is gone, which is exactly
# why the main-content figure is the one that decides.
def chrome_page(keep):
    nav = "".join(
        "<li><a href='/s%d'>Service number %d for every vehicle type</a></li>"
        % (i, i) for i in range(20))
    foot = "".join(
        "<p>Opening hours on day %d are eight in the morning until six.</p>"
        % i for i in range(20))
    main = "".join(
        "<p>Paragraph %d explains a part of the work in enough detail that "
        "a customer could decide whether to book it today.</p>" % i
        for i in range(keep))
    return ("<!doctype html><html><head><title>Workshop</title></head><body>"
            "<nav><ul>%s</ul></nav><main><h1>Workshop</h1>%s</main>"
            "<footer>%s</footer></body></html>" % (nav, main, foot))


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def run(tmp, old, new):
    p = subprocess.run([PY, "-X", "utf8", os.path.join(HERE, "parity.py"),
                        old, new, "--out", tmp],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tmp = tempfile.mkdtemp(prefix="parity_")
    try:
        f = {}
        for name, body in (("old", OLD), ("same", SAME), ("lossy", LOSSY),
                           ("shell", SHELL),
                           ("chrome_full", chrome_page(8)),
                           ("chrome_half", chrome_page(4))):
            f[name] = os.path.join(tmp, name + ".html")
            io.open(f[name], "w", encoding="utf-8", newline="\n").write(body)

        rc, out = run(tmp, f["old"], f["same"])
        ok("nothing lost -> exit 0", rc == 0, "rc=%d" % rc)
        ok("nothing lost -> says so", "accounted for" in out)
        ok("a reworded sentence is not a loss",
           "text block missing" not in out)
        ok("the same phone, formatted differently, is not a loss",
           "phone number missing" not in out)

        rc, out = run(tmp, f["old"], f["lossy"])
        ok("real losses -> exit 1", rc == 1, "rc=%d" % rc)
        ok("a missing heading is reported",
           "heading missing: Contact the workshop" in out)
        ok("a missing phone is reported", "phone number missing" in out)
        ok("a missing email is reported",
           "bookings@example-old.test" in out)
        ok("a missing form field is reported", "lost fields: vehicle" in out)
        ok("a missing image is reported", "fewer images" in out)
        ok("missing alt text is reported",
           "courtesy van" in out)
        ok("a missing outbound link is reported",
           "maps.example.test" in out)
        ok("missing structured data is reported",
           "structured data missing" in out)
        ok("losses are listed under MISSING", "MISSING - fix before" in out)

        rc, out = run(tmp, f["old"], f["shell"])
        ok("a client-rendered shell is never a pass", rc == 1, "rc=%d" % rc)
        ok("the shell case says what to do instead",
           "RENDERED html" in out and "CANNOT COMPARE" in out)

        rc, out = run(tmp, f["old"], os.path.join(tmp, "nope.html"))
        ok("an unreachable page is never a pass", rc == 1, "rc=%d" % rc)

        rc, out = run(tmp, f["chrome_full"], f["chrome_half"])
        ok("content lost behind a matching nav and footer -> exit 1",
           rc == 1, "rc=%d" % rc)
        ok("the whole-page figure alone would have missed it",
           "nav and footer included" in out and "(92%)" in out)
        ok("the main-content figure catches it",
           "main content coverage" in out and
           "4 text blocks from the old page are not on the new one" in out)
        ok("near-identical paragraphs cannot all match one survivor",
           out.count("text block missing") >= 4)

        rc, out = run(tmp, f["old"], f["same"])
        ok("a report file is written",
           os.path.isfile(os.path.join(tmp, "parity-report.md")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
