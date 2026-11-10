---
name: seo-complete
description: The SEO, schema and indexing rules this agency actually works to — title and meta limits, server-rendered JSON-LD, sitemaps built from data, internal links that resolve, HTML entities in the right fields, redirect hygiene, and multilingual parity. Use when building or editing any page, publishing a blog post, auditing a site, fixing 404s or redirects, touching a sitemap or schema, or whenever the user says SEO, schema, meta, breadcrumb, canonical, indexing, GEO or AEO.
---

# SEO, schema and indexing

Every rule here came from a live site where its absence caused a real problem.
Apply them at build time, not as a later pass.

## Titles, descriptions and H1

- `metatitle` **60 characters maximum**, `metadescription` **160 maximum** with
  **150 to 160 the target band**, `h1` **60 maximum**. None may end mid-word.
  All unique per page.
- A brand suffix (` | Brand Name`) is added **only if the whole title still fits
  60 characters**. Otherwise drop the suffix entirely. Never emit a partial or
  truncated brand name.
- **One separator in a title, not several.** `Main subject - Brand` reads; a
  title chopped into three or four segments by dashes and pipes does not.
- **Lead with the primary keyword** — in the first five words of the title, and
  inside the first 120 characters of the description, which is the part an AI
  overview is most likely to lift.
- **Avoid superlatives and boilerplate** - "Best", "Top", "Leading", a repeated
  keyword. Google rewrites titles it reads as padded, and then the title you
  wrote is not the title anyone sees.
- **Align the H1 with the title.** The closer they are, the less Google rewrites
  the title. Keep the primary keyword near the start of both.
- Include the city or region **only when the business actually targets one**.
  Skip it for multi-location and global brands unless the page itself leans on
  the location.
- One compelling call to action in the description, value first.
- **Leave blog and article titles alone** when auditing a site: they are written
  per post against the post's own intent, and a sitewide title pass should not
  rewrite them.
- If the current title, description or H1 already meets all of this, **say so
  and recommend nothing.** A recommendation that changes a correct tag is work
  the client pays for twice.
- In a second language, write real translated meta, not a machine echo of the
  English, and keep the brand transliteration identical everywhere on the site.

> The description limit was 155 here and is now 160, to match the agency
> guideline of a 150 to 160 band rather than sit just inside it and flag
> approved work as a defect. 160 is the gate; 150 to 160 is what to aim for.

### Changing a title carries a risk a description does not

This is the correction that matters most in this section, and it is the
opposite of what a checklist implies.

**A page that gets impressions is already ranking, and rewriting its title can
disturb that.** So on a live page, the default answer is **leave it alone**.
Change a title only for a stated reason - the keyword is absent, the intent is
wrong, it contradicts the H1 - and **length on its own is not a reason.** A
title at 68 characters that is ranking is worth more than a title at 58 that is
not. Never rewrite a blog or article title in a sitewide pass.

**A meta description does not affect ranking, so rewriting one risks nothing.**
That is where to spend the effort: write it for the person deciding whether to
click, not to a character count. Fitting the window is not the same as being
short, and if the current one is already strong, say "no change needed".

And the honest line to give the client once: **a page sitting at position 15 to
20 has a low click-through rate because it is on page two or three, not because
of its description.** Meta and FAQ work helps; ranking is the larger lever. Say
it once, plainly, and do not pad the report with it.

No year in a title. "(2026)" dates the page the moment the year turns.

So when the tool reports a title over 60 on a live site, that is a flag to look
at, not an instruction to rewrite.

## HTML entities — the field decides

Plain-text fields (`title`, `name`, `excerpt`, `metatitle`, `metadescription`,
`imagealt`) must hold **decoded** characters. `&amp;` in a title renders as the
literal five characters `&amp;` on the page — this reached a client screenshot.

`content` is HTML, so entities **belong** there: `&nbsp;`, `&rsquo;`, `&amp;`
inside content are correct and must not be "fixed".

When writing a publish or update path, decode entities in the plain-text fields
and leave content alone.

## JSON-LD

- Must be **server-rendered into the head**. Verify from the raw HTML with
  JavaScript never executed — `curl` it and look. A block that only appears
  after hydration does not count.
- One source of truth. If the template emits `BlogPosting` + `BreadcrumbList`,
  remove any inline `<script type="application/ld+json">` from the post body.
  Two Organization blocks on one page is a defect.
- Cover the page type: Organization or LocalBusiness, Service, Article or
  BlogPosting, FAQPage, and BreadcrumbList on every page below the root.
- **Link the nodes with `@id` instead of repeating them.** Declare the
  organisation once as `<site>/#organization`, then have `WebSite.publisher`,
  `LocalBusiness.parentOrganization` and `Service.provider` reference that id.
  A reference whose id nothing declares is a reference into nothing: the block
  reads as complete and resolves to no publisher at all.
- **`serviceType` belongs on `Service` only.** Not on `LocalBusiness`, not on
  `FinancialService`. It is ignored there, so the property looks present and
  does nothing.
- **Never ship a placeholder.** `[Business Name]`, `example.com`, `YOUR_`,
  `TODO`. Opening hours come from what the client actually gave, never a
  default of nine to five, and the logo URL is read off the live page rather
  than guessed. A placeholder in a live Organization block is read by the
  validator as the real value.
- **`FAQPage` questions must appear in the visible text.** Markup that answers
  questions the page does not ask is the one Google acts on.
- Only include `sameAs` social URLs that have actual values. An empty string in
  the array is worse than a shorter array.

## Sitemap

- **Build it from the data**, not from a hand-kept list, so a page can never
  exist without being listed. A hand-kept list has silently missed 9 live pages.
- URLs that **301 redirect never go in the sitemap**. They are correct as
  redirects; listing them is the error.
- Serve it at the canonical path with no trailing slash. `/sitemap.xml/` should
  redirect to `/sitemap.xml`, not serve a second copy.
- No duplicate URLs. Check the count before and after any change.
- A build step that overwrites `public/sitemap.xml` will defeat every source
  edit. Look for one before concluding a fix "did not publish".

## Internal links

- Every internal link must resolve to a page that exists. Target: **0 broken
  internal links**, checked against the real slug list.
- Author links with the **live URL**, not `/{slug}/`. A slug-shaped link that
  only works because a redirect catches it adds a hop to every new page.
- 3 to 4 internal links per article, natural and varied anchor text. Do not
  repeat the same exact-match keyword anchor across dozens of posts.
- Add a guard on the publish path that warns when a link target does not
  resolve. Warn, do not block — a redirecting link is avoidable, not an error.
- **Anchor text says where the link goes.** "Click here", "read more", "learn
  more" tell a reader and a crawler nothing.
- **No page should have zero internal links pointing at it.** A page reachable
  only from the sitemap is a page the site itself does not vouch for. Count
  inbound links from content, not from the navigation: the nav links every page
  and so distinguishes none of them.

### Where a new internal link may be placed

This is the rule that gets broken most often, and it is about the **source**
page, not the destination.

> **Links are placed on editorial content only** — blog posts, articles, learn
> and resources pages, news, guides. **Never on** the home page, a service
> page, about, contact, team, pricing, legal, a landing page, or a category and
> archive hub such as `/blog/` itself.

Destinations are unrestricted: an article may link to anything. The common and
most valuable direction is article to service page, then article to related
article, then article to contact.

Two rules that follow from it:

- **The anchor text must already exist, word for word, in the article body.**
  Find the phrase in the live page and link it. Never write a plausible
  sentence to hang a link on, and never link from a heading or a button. If no
  suitable phrase exists on the page, there is no suggestion — say so rather
  than inventing one.
- **Check what is already linked before proposing anything.** A link that is
  already on the page, including in a "related posts" block, is recorded as
  existing, not re-proposed.

Group the site by the first path segment to see its silos, and prioritise by
what actually gets traffic: the articles with clicks in Search Console are the
ones worth linking from and to. That ordering needs GSC and is not something
the tool can read on its own.

## One canonical address, proved on all four variants

A site is reachable four ways and only one of them may answer 200:

| Request | Expected |
|---|---|
| `https://domain/` | 200, or 301 to the www form if that is canonical |
| `http://domain/` | 301 to https |
| `https://www.domain/` | 301 to the non-www form, or 200 if www is canonical |
| `http://www.domain/` | 301 to the final canonical address |

**Two variants both answering 200 is a duplicate-content defect**, and it is the
one nobody notices because every variant looks fine on its own. Test all four,
and check the `rel=canonical` on each one points at the same single address.
`og:url` must match it too.

## Indexability

- Read the robots `<meta>` **and** the `X-Robots-Tag` response header. A page
  can be noindexed by a header while its markup looks clean, which is how a
  staging flag survives a launch.
- Check `max-snippet`, `max-image-preview` and `max-video-preview` if they are
  set at all; a restrictive `max-snippet` quietly shrinks every result.
- **An invalid URL must return a real 404.** A single-page app answers 200 with
  its own shell for every unknown path, so Google indexes infinite soft 404s and
  a genuinely missing page never reports itself. Request a URL that cannot
  exist and check the **status code**, not what the page looks like.
- Keep `noindex` on private routes, studio or admin pages, and client-preview
  pages - and confirm it is gone from production before launch.

## Redirects and 404s

- Prefer a **rule** over hand-written entries: "for every row, `/{slug}/` 301s
  to that row's old URL when the two differ" stays correct when rows are added.
- A redirect whose destination 404s is worse than no redirect. Point it at a
  real page or remove it so the URL fails honestly.
- Exclude `/assets/` from any catch-all route. A missing asset must return a
  real 404 with a JavaScript content type, never a 301/307 chain into HTML.
  Asset hashes are case-sensitive, so a lowercasing redirect corrupts them.
- Keep `noindex` on private routes, studio or admin pages, and client-preview
  pages.
- On a cluster of cannibalising posts, keep the longest as canonical and 301 the
  retired slugs to it.

## Images

- `alt` on every content image, describing the image. Decorative images get
  `alt=""`. Never use the filename.
- Never depend on a third-party placeholder image service in production — one
  failed and broke 87 pages.

## Content quality, as far as it can be measured

The quality-focused updates act on this, and three parts of it are countable
rather than a matter of taste.

- **Thin pages.** Under 300 words on a page that is meant to rank. Contact,
  thank-you, privacy and archive pages are exempt - they are not competing on
  depth.
- **Keyword stuffing.** One term taking more than about 6% of a page's words
  reads as stuffing rather than as writing. Natural prose almost never puts a
  single non-stopword above 2%. Report the term and the share, not an opinion.
- **Hidden text that links off-site.** Substantial text a visitor cannot see,
  outside any menu or dialog, whose links leave the site. **This one is a
  compromise until proven otherwise** - look for modified files and unknown
  admin users, and check whether the pages are indexed, before deleting
  anything.

Two false positives to stay clear of, both found by running this against real
sites rather than fixtures:

- **A collapsed menu is hidden text.** So is a dropdown, an accordion, a tab
  panel, a modal and a skip link. A documentation site reported 191 hidden
  words across 6 elements carrying 43 links, and every one was navigation.
  What separates an injection is that it sits outside any interface component
  **and** its links point away from the site.
- **A real site uses its own vocabulary.** A pharmacy says "pharmacy" and a
  casino review site says "casino". Spam-vertical wording is a weak secondary
  signal, never a conclusion on its own.

## NAP, for a business with one address

Name, address and phone have to be identical everywhere: page copy, header,
footer, contact and about blocks, the map embed, and the local schema. A
mismatch splits the business's local signals.

Audit in this order, because each step changes what the next one means: **name,
then phone, then address, then the map pin, then the schema.**

- **The confirmed values are the source of truth**, and they come from the
  client. Never infer them from the site - the site is the thing being audited.
  If they are not written down, ask for them before starting.
- **Be granular on the address.** A wrong ZIP, a missing suite, "Ste" against
  "Suite", "W Carmel Dr" against "West Carmel Drive" - each one is a finding on
  its own.
- **More than one phone number across the site is a finding**, but a second
  number can be legitimate - a fax, a department line. Flag it for the client to
  confirm rather than picking one.
- **The schema's `name`, `telephone` and `address` must match the visible
  NAP.** Schema that disagrees with the page is worse than no schema.
- Audit and record; do not edit. Implementing the fixes is a separate pass with
  its own approval.
- Confirm a sample of findings against the live page before reporting them, so
  the list carries no false positives.

`seo.js` reports the part that needs no source of truth: **whether the site
agrees with itself.** If three different phone numbers appear across the pages
it read, or the schema's telephone matches none of them, that is a finding
whichever one turns out to be correct.

## Keywords, when there is keyword data

The tooling for this lives outside here, but two rules travel with it:

- **Verify the target locations from the site before researching anything.**
  Take them from the sitemap and the existing location pages, never from which
  cities happen to have volume. A location keyword maps to a page that exists
  or is planned, and that page's URL is recorded against it. A location page
  whose keywords carry almost no volume gets flagged, not padded with weak
  terms.
- **What to exclude by default:** the client's own brand, anything two words or
  shorter, and "near me". But **"local SEO" as a service term is not a "near
  me" keyword** - someone searching "best local seo agency" is a business owner
  hiring, not a consumer looking for something nearby. Confusing the two drops
  the client's most commercial keywords.

Quick wins have a definition worth using: **position 6 to 20 with 100 or more
impressions.** Those are pages one good change away from page one.

Never apply one country's search volumes to another country's pages.

## Competitors

- **Pick them for relevance** - same niche, same city or region, similar
  services - and confirm the list with the client before analysing anyone. The
  tool's idea of a competitor is whoever overlaps on keywords, which is often
  somebody the client has never heard of.
- Two things are measurable without any paid tool and are usually the most
  useful: **whether each competitor is actually publishing** (does a blog
  exist, how often, when was the last post, which of them are dormant), and
  **what their negative reviews say repeatedly** - billing, wait times, staff,
  hours. Each recurring complaint is a thing the client can be better at, which
  is a content and positioning brief rather than a statistic.
- One backlink per referring domain, deduplicated, with spam TLDs dropped.
  Counting the same domain fifty times flatters everyone.

## Multilingual

- Tag-count parity between languages across `<h2> <h3> <h4> <ul> <ol> <li> <a>`
  must be **0 mismatches**. Any structural edit goes into both language fields
  in the same write.
- A prose-only edit must not move any tag count. If a count moves, something
  else was changed.
- Do not leave Latin brand text inside RTL prose; use the translated rendering
  except in URLs and proper nouns with no local form.

## GEO / AEO — being quotable by AI answers

- Answer the page's question in the **first paragraph**, directly, before any
  build-up. Answer engines quote the opening.
- One clear idea per heading, phrased as the question a person would ask.
- Facts with numbers, dates and named sources are quotable; vague claims are
  not. Never invent a figure to fill the gap.
- `FAQPage` schema on pages with real questions, matching visible on-page text.
- Keep entity names consistent sitewide — same company name, same spelling,
  same service names.
- **Check robots.txt does not block the AI crawlers.** Being quotable means
  being fetchable: `GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`,
  `Bytespider`. A blanket block, or a `Disallow` under one of their user-agent
  blocks, removes the site from AI answers entirely while leaving Google search
  untouched - so nothing in the client's search reporting shows it.
  Blocking them can be a deliberate decision. Make sure it was one.

## Before claiming the SEO work is done

```bash
node "C:\Claude-Code\.ai-system\skills\seo-complete\seo.js" <url> \
  --out <project>\.claude-context\qa\seo [--pages 25] [--no-links]
```

Check and report the numbers, not an impression. The tool produces every one of
these; for a long time this section demanded them and shipped nothing, so they
got eyeballed instead, which is the exact failure the rest of this system exists
to prevent:

- internal links whose target does not resolve: must be 0
- `metatitle` over 60 or `metadescription` over 160 or `h1` over 60: must be 0
- pages with no canonical, no H1, or more than one H1: must be 0
- pages whose JSON-LD is missing from the **raw** HTML: must be 0
- literal entities in plain-text fields: must be 0
- sitemap unique URL count, and that it contains no redirecting URLs
- the four address variants, with exactly one answering 200
- an invalid URL returning a real 404 rather than the app's shell
- the AI crawlers not blocked in robots.txt
- which schema types exist across the site, blocks that are not valid JSON,
  duplicate Organization or WebSite nodes, `@id` references that resolve to
  nothing, placeholders, and FAQ questions absent from the visible text
- pages nothing links to, articles carrying fewer than three in-content links,
  anchor text repeated across five or more pages, and non-descriptive anchors

**It will not call a page an orphan from a partial crawl.** A page linked only
from pages that were not read would look orphaned, so below full sitemap
coverage - or with no readable sitemap at all - the count is withheld and the
report says which it was. A number that looks authoritative and is not is worse
than no number.

It reads the **raw** HTML for the things that must be server-rendered, and the
rendered DOM for the things a visitor sees, because those are different
questions and one fetch cannot answer both.

**Two rules about reporting it**, both learned the hard way elsewhere and both
worth keeping here:

- A 403 or a rate-limit is **not** a missing page. Say "blocked" and say which
  identity was refused; never fold it into the broken count.
- When a value cannot be read, write **Missing**. Never "Not Detected", "Not
  Found", "N/A" or a placeholder: those read as findings and get fixed by
  someone who then discovers there was nothing wrong.

Link checking is capped and prioritises navigation, footer and in-content links.
When the cap bites, the report says so rather than implying the whole site was
crawled.
