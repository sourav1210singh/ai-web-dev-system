---
name: launch-files
description: The small files a site is launched without and then nobody notices — favicon (the real .ico, not just head tags), llms.txt, robots.txt, sitemap and og:image — plus the rule that every one of them must carry the live domain, never a lovable.app or preview URL. Use before any go-live, after a domain is pointed, when a platform's default icon is still showing, or when asked about favicon, llms.txt, robots.txt, sitemap or share image. Triggers on "favicon", "llms.txt", "robots.txt", "sitemap", "og image", "share image", "go live", "launch checklist".
---

# Launch files

## Making the share card

```bash
python "C:\Claude-Code\.ai-system\skills\launch-files\ogcard.py" <photo> <out.jpg> --logo <logo.png>
```

1200x630 from a photo the site already owns, with a gradient scrim so the logo
reads over it. Not a screenshot of the homepage: that is the wrong ratio, it
goes stale the moment the page changes, and it carries whatever placeholder
text was on the page that day.

Then look at it. A card can measure correctly and still read badly. The first
one built for a site this week was 1200x630, inside budget, and unusable: a
white logo on bright concrete.

These are small, they are always left to last, and the favicon one is hard to
undo once Google has cached it.

## Check what is actually there first

```bash
python "C:\Claude-Code\.ai-system\skills\launch-files\check.py" <domain> [<domain> ...]
```

Reports favicon, robots.txt, llms.txt, sitemap.xml and og:image for each
domain, and flags any that points at the wrong host.

**It tries several identities before reporting a failure.** A measured example
on a live client site: a fake Chrome user agent gets HTTP 403, curl's own
default user agent gets 200, and Googlebot gets 200. A refusal for one identity
proves nothing about whether the file exists. The tool now reports
"BLOCKED" separately from "MISSING (404)", and so should you.

## Favicon

A platform starter ships its own icon at `public/favicon.ico`. Lovable's is the
heart.

**Adding `<link rel="icon">` tags to the head does not replace that file.**
Browsers and Google request `/favicon.ico` directly, so the platform icon keeps
appearing no matter what the head says.

Replace the file itself, and ship the full set. This is what a complete
`public/` looks like, taken from a project that got it right:

```
public/
  favicon.ico              real multi-size ICO (16, 32, 48)
  favicon.png
  favicon-16x16.png
  favicon-32x32.png
  favicon-48x48.png
  apple-touch-icon.png     180x180
  android-chrome-192x192.png
  android-chrome-512x512.png
  site.webmanifest
  robots.txt
  llms.txt
  og/                      one share image per page, on your own domain
```

Plus the matching head tags. The `og/` folder is worth copying: a share image
per page, served from the site's own domain, instead of one generic image on a
preview URL.

**Do this before the domain goes live.** Once Google has cached the starter
icon it takes days to weeks to change, and there is nothing to do but wait.

Verify two ways:

1. `https://<domain>/favicon.ico` in an incognito window — the brand icon, and
   a file with a non-zero size. One client site is currently serving a **0
   byte** favicon, which the browser silently falls back from.
2. `https://www.google.com/s2/favicons?domain=<domain>&sz=64` — what Google
   has.

## The live-domain rule

`og:image`, the sitemap and `llms.txt` must all carry the **real** domain.

Preview and build URLs leak into these constantly: `*.lovable.app`, an
`*.r2.dev` object URL, a staging subdomain. A share image on a preview URL
means every link shared on WhatsApp, LinkedIn or Slack points at a host the
client does not own and may stop resolving.

Two live client sites are doing this right now, so check it every time.

## llms.txt

There is no "llm.txt". The file is `/llms.txt`, in the llmstxt.org format: a
short plain-text index of the site for AI answer engines. An optional
`/llms-full.txt` carries the whole text; skip it unless asked.

Build it only from what is already on the site. Never invent a price, a number,
a claim or a service. Only link pages that return 200, with full URLs and the
same trailing-slash style the site uses, in the site's own language.

### The reference implementation

One site in this workspace has the version to copy the shape of. What makes it
work is that it answers the questions a person actually
asks an assistant, as facts rather than marketing:

- **One `>` paragraph**: what the business does, where, for whom, and the offer.
- **A contact and key-facts block**: full address, phone and WhatsApp, email,
  opening hours by day, the service area named town by town, and whether travel
  is charged.
- **Ratings with their source and count** — "5.0 from 122 Google reviews, 4.91
  on ProvenExpert". A rating with no source is not quotable.
- **A dated price block** — "Prices (fixed, as of October 2026)" with the real
  figures, the minimum order value, and what needs an individual quote. The
  date matters: an assistant quoting it later should be able to see its vintage.
- **The operational answers**: the method used, how long until the furniture is
  usable again, which payment methods for private versus business customers.
  These are exactly what gets asked and almost never published.
- **Then `## Section` lists** of `[Page title](full URL): one short line`.

If a fact is not already on the site, it does not go in llms.txt. Put it on the
site first, or leave it out.

### The LLM-Info page

Alongside the machine file, publish the same content as a human-readable page
at `/llms-info/`, and link it in the footer next to the imprint or privacy
link.

It costs nothing extra, it gives the client something they can actually see and
check, and it makes the same facts crawlable as a normal page rather than only
as a text file many crawlers ignore.

Prompt for it, after llms.txt exists:

```
Create an LLM-Info page at /llms-info/ holding the same key facts as
public/llms.txt, written as a normal page in the site's own components and
language. Add a footer link labelled "LLM-Info" immediately to the left of the
Impressum link. Do not change any other page, component, style, form or route.

Make the change and stop. Do not run tests or curl commands. Do not poll the
backend. Do not write a report.
```

## The prompt for a Lovable project

Fill in `[DOMAIN]` and the business details before sending. Note the closing
lines — see the `lovable-prompting` skill for why they matter.

```
Add a correct llms.txt and robots.txt to this website.

Live domain: https://[DOMAIN]   (use this address everywhere, never the
lovable.app address)

1. public/robots.txt (replace the existing one if there is one) with exactly:

User-agent: *
Allow: /
Disallow: /admin
Disallow: /api/
Sitemap: https://[DOMAIN]/sitemap.xml

Remove the two Disallow lines for paths that do not exist in this project. Do
not block CSS, JavaScript or images. If robots.txt is also generated by a route
or a build step, keep only one source so the file at /robots.txt is this one.

2. public/llms.txt (plain text, UTF-8) in the llmstxt.org format:

# [Business name]

> [One or two sentences: what the business does, where, and for whom.]

Key facts (only facts that already appear on this website, word for word where
possible):
- Address, phone, e-mail, opening hours
- Service area
- Ratings, only if they are shown on the website

## Services
- [Page title](https://[DOMAIN]/[path]/): one short line about the page
(one line for every service page)

## Company
- [About / Prices / Reviews / Contact pages, same format]

## Optional
- [Blog](https://[DOMAIN]/blog/)
- [Imprint, privacy policy]
- [Sitemap](https://[DOMAIN]/sitemap.xml)

Rules for llms.txt:
- Only use information that is already on the website. Do not invent prices,
  numbers, claims or services.
- Only link pages that exist and return 200. Use full URLs with
  https://[DOMAIN] and the same trailing slash style as the site.
- Write it in the same language as the website.

Do not change any page, component, style, form or route besides these two
files.

If this cannot be done as described, stop and say so in one sentence.

Make the change and stop. Do not run tests or curl commands. Do not poll the
backend. Do not write a report.
```

## After publishing

Open all three in a browser. Each must show text, not an error and not the
homepage:

- `https://<domain>/robots.txt` — last line is the sitemap, on the real domain
- `https://<domain>/llms.txt` — business info and links
- `https://<domain>/sitemap.xml`

Click a few of the llms.txt links and confirm they open. Then run `check.py`
again and compare against the run from before the change.

A site that returns the homepage for `/robots.txt` has a catch-all route eating
it — the file is not being served at all. See the `seo-complete` skill.
