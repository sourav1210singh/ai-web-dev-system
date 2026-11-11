# -*- coding: utf-8 -*-
"""Does check.py tell a refusal from a missing file, and a wrong domain from
a right one?

check.py was the second tool built here and went three weeks with no suite.
It is a check in both the `fix` and `intake` job types, and `jobtest.py`
replaces it with a stub, which is the right call for testing a state machine
and means nothing had ever exercised the tool itself.

Two halves, because they fail in different ways:

  - the transport, against a real local server, including the escalation that
    exists only because a live client site answered 403 to a browser user
    agent and 200 to curl's own
  - the decisions, with the transport replaced, because "a 403 is not a
    missing file" is a judgement about an answer, not a network event
"""
import http.server, os, socket, subprocess, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check

RESULTS = []
ROUTES = {}


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


class Handler(http.server.BaseHTTPRequestHandler):
    """Serves by path, and can insist on a particular user agent.

    A WAF that refuses one identity and serves another is the whole reason
    check.py escalates, so the server under test has to be able to do it.
    """
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def do_GET(self):
        rule = ROUTES.get(self.path)
        if rule is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not here")
            return
        status, body, ctype, need_ua = rule
        if need_ua and need_ua.lower() not in \
                (self.headers.get("User-Agent") or "").lower():
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"refused")
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve():
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def fake_transport(mapping):
    """Stand in for get(), so the decisions can be tested without a network."""
    def _get(url, binary=False):
        v = mapping.get(url)
        if v is None:
            return check.Resp(404, b"not here")
        status, body = v
        if isinstance(body, str):
            body = body.encode("utf-8")
        return check.Resp(status, body, "text/plain")
    return _get


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    # --- the transport, against a real server ---------------------------
    ROUTES["/plain.txt"] = (200, b"hello", "text/plain", None)
    # 403 to anything that is not curl's own identity, which is the shape
    # measured on a live client site: fake Chrome 403, curl 200.
    ROUTES["/waf.txt"] = (200, b"served to curl", "text/plain", "curl")
    # and the harder one, where only Googlebot is let through
    ROUTES["/bot.txt"] = (200, b"served to googlebot", "text/plain", "Googlebot")
    srv, base = serve()
    try:
        r = check.get(base + "/plain.txt")
        ok("a served file comes back 200 with its body",
           r is not None and r.status_code == 200 and b"hello" in r.content,
           "" if r is not None else "no response")

        r = check.get(base + "/missing.txt")
        ok("a file that is not there comes back 404",
           r is not None and r.status_code == 404)

        r = check.get(base + "/waf.txt")
        ok("a 403 for the browser identity escalates to curl and succeeds",
           r is not None and r.status_code == 200 and b"curl" in r.content,
           "got %s" % (r.status_code if r is not None else None))

        r = check.curl(base + "/bot.txt")
        ok("curl keeps trying identities until one is served",
           r is not None and r.status_code == 200 and b"googlebot" in r.content,
           "got %s" % (r.status_code if r is not None else None))

        dead = "http://127.0.0.1:%d/x" % closed_port()
        r = check.get(dead)
        ok("a host that cannot be reached is not reported as a 404",
           r is None or r.status_code != 404,
           "status %s" % (r.status_code if r is not None else None))
    finally:
        srv.shutdown()

    # --- what each answer MEANS -----------------------------------------
    # The README's fifth principle in one function: a 403 is not "the site is
    # down" and it is not a missing file. It may well be serving everyone
    # else normally.
    ok("403 reads as blocked, not missing", "BLOCKED" in check._why(
        check.Resp(403, b"")) and "MISSING" not in check._why(check.Resp(403, b"")))
    for code in (401, 406, 429, 503):
        if "BLOCKED" not in check._why(check.Resp(code, b"")):
            ok("every refusal code reads as blocked", False, "HTTP %d" % code)
            break
    else:
        ok("every refusal code reads as blocked", True, "401, 406, 429, 503")
    ok("404 reads as missing", check._why(check.Resp(404, b"")) == "MISSING (404)")
    ok("no response at all says so plainly",
       "could not be fetched" in check._why(None))
    ok("an unexpected code is reported as itself",
       "500" in check._why(check.Resp(500, b"")))

    # --- the decisions ----------------------------------------------------
    real_get = check.get
    try:
        d = "example.com"
        b = "https://" + d
        check.get = fake_transport({
            b + "/favicon.ico": (200, b"\x00\x01icon"),
            b + "/robots.txt": (200, "User-agent: *\nSitemap: https://example.com/sitemap.xml\n"),
            b + "/llms.txt": (200, "# Example\nhttps://example.com/about\n"),
            b + "/sitemap.xml": (200, "<urlset><loc>a</loc><loc>b</loc><loc>c</loc></urlset>"),
            b + "/": (200, '<meta property="og:image" content="https://example.com/og.jpg">'),
        })
        o = check.row(d)
        ok("a clean site reports a favicon with its size and hash",
           "bytes" in o["favicon"] and "md5" in o["favicon"], o["favicon"])
        ok("a sitemap line on the right domain raises nothing",
           "WRONG DOMAIN" not in o["robots"], o["robots"])
        ok("llms.txt linking only to itself raises nothing",
           "links to" not in o["llms"], o["llms"])
        ok("the sitemap's URLs are counted", o["sitemap"] == "3 URLs", o["sitemap"])
        ok("an og:image on the right domain raises nothing",
           "WRONG DOMAIN" not in o["og_image"], o["og_image"])

        check.get = fake_transport({
            b + "/favicon.ico": (404, b""),
            b + "/robots.txt": (200, "Sitemap: https://someone-else.com/sitemap.xml\n"),
            b + "/llms.txt": (200, "# Example\nhttps://preview.lovable.app/about\n"),
            b + "/sitemap.xml": (403, b""),
            b + "/": (200, "<html><head><title>x</title></head></html>"),
        })
        o = check.row(d)
        ok("a missing favicon is reported as missing",
           "MISSING" in o["favicon"], o["favicon"])
        ok("a sitemap line pointing at another domain is caught",
           "WRONG DOMAIN" in o["robots"], o["robots"])
        ok("llms.txt pointing at a preview domain is caught",
           "links to" in o["llms"] and "lovable" in o["llms"], o["llms"])
        ok("a refused sitemap is not reported as having no URLs",
           "BLOCKED" in o["sitemap"] and "0 URLs" not in o["sitemap"],
           o["sitemap"])
        ok("a page with no og:image says so", o["og_image"] == "not set",
           o["og_image"])

        check.get = fake_transport({
            b + "/robots.txt": (200, "<html><body>404 page</body></html>"),
            b + "/llms.txt": (200, "<HTML><body>soft 404</body></HTML>"),
            b + "/sitemap.xml": (200, "<urlset></urlset>"),
            b + "/": (200, '<meta property="og:image" content="https://cdn.other.net/og.jpg">'),
            b + "/favicon.ico": (200, b"icon"),
        })
        o = check.row(d)
        ok("a robots.txt that is really an HTML page is caught",
           "NOT A FILE" in o["robots"], o["robots"])
        ok("an llms.txt that is really an HTML page is caught too",
           "NOT A FILE" in o["llms"], o["llms"])
        ok("an og:image served from another domain is caught",
           "WRONG DOMAIN" in o["og_image"], o["og_image"])
        ok("an empty sitemap is reported as empty rather than missing",
           o["sitemap"] == "0 URLs", o["sitemap"])

        # robots.txt with no Sitemap line at all
        check.get = fake_transport({b + "/robots.txt": (200, "User-agent: *\nDisallow:\n")})
        ok("a robots.txt that declares no sitemap says so",
           "NOT DECLARED" in check.row(d)["robots"])

        # www is stripped before the domains are compared, or every www site
        # would report its own sitemap as the wrong domain
        w = "www.example.com"
        bw = "https://" + w
        check.get = fake_transport({
            bw + "/robots.txt": (200, "Sitemap: https://example.com/sitemap.xml\n"),
        })
        ok("a www domain does not report its own sitemap as foreign",
           "WRONG DOMAIN" not in check.row(w)["robots"],
           check.row(w)["robots"])
    finally:
        check.get = real_get

    # --- the command line -------------------------------------------------
    p = subprocess.run([sys.executable, "-X", "utf8",
                        os.path.join(HERE, "check.py")],
                       capture_output=True, text=True)
    ok("no arguments prints the usage and exits non-zero",
       p.returncode == 2 and "check.py" in (p.stdout or ""),
       "rc=%d" % p.returncode)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
