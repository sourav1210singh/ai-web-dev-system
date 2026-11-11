---
name: security-pass
description: Check whether a site is safe to put live, measured rather than assumed. The transport headers (HSTS, CSP, framing, referrer policy), TLS, mixed content, cookie flags, published source maps, and whether a secret key has been shipped into the browser bundle, with the four Supabase key types told apart so the two that are meant to be public are not reported. Plus the short fixed list of files that must never be readable (.env, .git, config backups). Also what to do when a key really has leaked, which is not what most people do. Use before any go-live, after any deploy that rebuilds the bundle, at the start of a new client, and when a client asks whether their site is secure. Triggers on "security", "secure hai", "safe hai kya", "headers check karo", "CSP", "HSTS", "SSL", "certificate expired", "key leak ho gayi", "api key", "service_role", "mixed content", "vulnerability", "pentest", "hack ho gaya", "site safe hai".
---

# Security pass

## Run it

```bash
node "C:\Claude-Code\.ai-system\skills\security-pass\security.js" <url> --out <project>\.claude-context\qa\security
```

It writes `security.md` and `security.json`, and exits 1 if anything it found is
a blocker. `--no-probe` skips the file probes; `--max-scripts N` changes how
many bundle files are read (25 by default).

One page load in a real browser, then it reads what the server actually sent:
the response headers, the cookies, every subresource, the body of every
same-origin script, and seven fixed paths.

`fix-job` already runs it as one of the checks for **golive**, **intake** and
**watch**, so a launch gate does not need it called separately.

## Only on a site you have been asked to work on

The probe list is seven GETs for files that are catastrophic when served. That
is a reasonable thing to do to a client's own site before launching it, and not
a reasonable thing to do to anybody else's. Point this at the site the user
nominated and nowhere else. It does not fuzz, guess filenames, try passwords or
send anything but GET requests, and it must stay that way: the moment the list
grows it stops being a pre-launch check and becomes a scanner.

## What it checks, and why each one matters

| Finding | Why it matters |
|---|---|
| No https, or an invalid certificate | Everything typed into the enquiry form crosses the network in the clear. An expired certificate is reported and the pass continues, so you get the rest of the picture in one run. |
| http does not redirect to https | A visitor who types the bare domain never reaches the secure site. |
| HSTS missing or short | OWASP's recommended header is `max-age=63072000; includeSubDomains; preload`. Under a year is reported as short. `preload` is consent to be added to the browser list; submitting the domain is a separate step the owner does. |
| No CSP, or one that controls no scripts | Nothing limits what an injected tag may run. Reported as major, never as a blocker, see below. |
| Page can be framed by anything | No `X-Frame-Options` and no `frame-ancestors`. The page inside someone else's wrapper can harvest what a visitor types. |
| Mixed content | Checked three ways, because one is not enough: the browser upgrades a passive http subresource before it reaches the network log and blocks active ones outright, so a network-only check sees a clean page while the markup still says `http://`. |
| Cookie flags | A session cookie without `Secure` or without `HttpOnly`. Ordinary third-party cookies are grouped into one line, because a consent banner and a tag manager set five of them and five identical lines push the real finding off the top. |
| A secret key in the bundle | The one that actually costs money. See below. |
| Published source maps | Only reported when the `.map` is really served. The comment surviving in a bundle whose map 404s is the normal, fine case. |
| A form posting over http or off-site | The lead's own data. This is the `forms-and-leads` privacy rule, measured. |
| `/.env`, `/.git/config`, `/.git/HEAD`, `/wp-config.php.bak`, `/.htaccess`, `/phpinfo.php`, `/server-status` | Reachable, they hand over the database, the repository or the server. |

### A missing CSP is major, not a blocker

A brochure site with no Content-Security-Policy is the normal state of the web.
A launch gate that refuses to open for it is a gate people learn to force, and
then it stops stopping the things that should stop a launch. Only the blockers
hold a launch: no https, an invalid certificate, active mixed content, a form
posting in the clear, a readable `.env`, a key in the bundle.

## The four Supabase keys, because two of them are meant to be public

This is the difference between a usable check and one that fires on every
Supabase site. From Supabase's own documentation:

| Key | In the browser? |
|---|---|
| `sb_publishable_...` | **Fine.** Documented as safe to expose in a web page, an app, source code. |
| `sb_secret_...` | **Never.** Bypasses row level security entirely. |
| legacy `anon` (a JWT starting `eyJ`) | **Fine.** The old form of the publishable key. |
| legacy `service_role` (a JWT starting `eyJ`) | **Never.** The old form of the secret key. |

The two legacy keys are both long-lived JWTs starting `eyJ` and nothing about
their shape tells them apart, so the tool decodes the payload and reads the
`role` claim. A scanner that matches on `eyJ` either flags every Supabase site
or none of them. The legacy pair is deprecated at the end of 2026 and both
systems work at once until then, so all four are checked.

And the thing the key check cannot tell you: the publishable key only protects
anything if the tables have row level security policies. A public key over an
unprotected table is a public table. That is a database question, not a header
question. Ask it.

## When a key really has leaked, rotate before you tidy

The instinct is to delete the key from the source and rebuild. That fixes
nothing on its own, and getting the order wrong is how a leak becomes an
incident:

**A key in a shipped bundle is already public.** It is in the CDN's cache, in
the browser cache of everyone who visited, in the git history, and quite
possibly in a web archive. Anyone who already took it keeps working access
after you remove it.

So:

1. **Issue a new key and switch the server over.** First, before anything else.
2. **Revoke the old one.** Until this is done nothing has been fixed.
3. Then remove it from the source, move it to a server-side environment
   variable, and rebuild.
4. Check what the key could reach, and say so plainly. A leaked Supabase secret
   or `service_role` key is not "someone could read a table". It bypasses row
   level security, so it is read and write on every table, including every
   other customer's personal data. That is a same-day conversation with the
   client, not a line in a monthly report.
5. Write the date, the key's purpose and where the new one lives into the
   project memory. Never the value.

## Never quote the secret

Every finding reports the pattern, the file, a masked fragment and a short
one-way fingerprint. It never prints the key, and the `.env` finding never
reproduces the file's contents.

This is not tidiness. A report that quotes what it found has copied the leak
into the project folder, into the chat, and into whatever the client is sent -
and those are places the key was not before. The fingerprint exists so the same
key found in four files collapses to one finding while two different keys that
mask identically stay two findings. Measured on a live site: three different
Google keys all mask to `AIza...**** (39 chars)`, so collapsing on the mask
would have hidden two of them.

## Three things it deliberately does not report

Adding these back would be a step backwards. They are what a scanner emits and
a developer learns to ignore.

- **`target="_blank"` without `rel="noopener"`.** Every current engine implies
  `noopener` for a `_blank` anchor and the behaviour is in the HTML standard -
  Safari from 2018, Firefox 79, Chromium 88. Reporting it sends somebody to
  edit a hundred links for nothing.
- **`X-XSS-Protection`.** Deprecated and removed from the engines that had it,
  and its filter introduced bugs of its own.
- **Missing `integrity` on a tag manager or analytics script.** Those are
  loaders whose content is meant to change, so SRI cannot apply to them by
  design. What is worth saying is the count: every third-party script can
  change the page whenever its owner changes it, and the report lists the
  origins so that is a decision rather than a surprise.

## What it does not cover

Say this when handing over a report, because the gap between what was checked
and what a client hears is where trust goes:

- One load, one machine, one page. Run it on the home page **and** a form page.
- It reads the outside of the application. It does not test sign-in, access
  control, whether one logged-in user can read another's data, file uploads,
  SQL injection, or the database's own rules. **It is not a penetration test**
  and should never be described as one.
- It says nothing about dependency versions or known CVEs in the bundle.
- A development origin (`localhost`, `127.0.0.1`, `*.test`) has its transport
  checks skipped rather than failed, so a clean run there is not a clean run in
  production.

## Running the tests

```bash
node "C:\Claude-Code\.ai-system\skills\security-pass\sectest.js"
```

92 checks. The ones worth keeping green above all others: the Supabase
publishable and legacy `anon` keys must not be reported, no report may contain a
secret it found, and a 200 that is really the app's own HTML must not be
reported as a readable file, because a single-page app answers 200 for every
unknown path, and trusting the status code reports seven breaches on a site
that has none. The same trap already caught this workspace once with robots.txt.

One thing to know before editing the pattern table: `security.js` assembles the
private-key pattern from two strings instead of writing it out, because
`leakcheck.py` looks for that exact line and would otherwise report this file as
carrying a private key. Keep it assembled, and keep fake keys in the tests out
of variables named `token`, `secret` or `password`, for the same reason.
