---
name: seo-complete
description: The SEO, schema and indexing rules this agency actually works to — title and meta limits, server-rendered JSON-LD, sitemaps built from data, internal links that resolve, HTML entities in the right fields, redirect hygiene, and multilingual parity. Use when building or editing any page, publishing a blog post, auditing a site, fixing 404s or redirects, touching a sitemap or schema, or whenever the user says SEO, schema, meta, breadcrumb, canonical, indexing, GEO or AEO.
---

# SEO, schema and indexing

Every rule here came from a live site where its absence caused a real problem.
Apply them at build time, not as a later pass.

## Titles and descriptions

- `metatitle` **60 characters maximum**, `metadescription` **155 maximum**.
  Neither may end mid-word. Both unique per page.
- A brand suffix (` | Brand Name`) is added **only if the whole title still fits
  60 characters**. Otherwise drop the suffix entirely. Never emit a partial or
  truncated brand name.
- In a second language, write real translated meta, not a machine echo of the
  English, and keep the brand transliteration identical everywhere on the site.

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

## Before claiming the SEO work is done

Check and report the numbers, not an impression:

- internal links whose target does not resolve: must be 0
- `metatitle` over 60 or `metadescription` over 155: must be 0
- pages with no canonical, no H1, or more than one H1: must be 0
- pages whose JSON-LD is missing from the **raw** HTML: must be 0
- literal entities in plain-text fields: must be 0
- sitemap unique URL count, and that it contains no redirecting URLs
