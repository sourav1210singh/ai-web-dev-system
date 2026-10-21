---
name: client-content-audit
description: Audit what the client actually sent before building anything — what is complete, what is thin, what is truncated, what was never sent — and refuse to publish content that would hurt the site. Produces a gap report, a list of what to ask for, and reserved slugs for pages that are blocked. Use when a client sends documents, a content pack, a brief or attachments, and before starting any build from supplied content. Triggers on "client ne content bheja", "ye docs dekho", "content audit", "kya missing hai", "build from this", "client ka brief".
---

# Auditing what the client sent

Building from a content pack without reading it first is how a site ends up
with three good pages and two that damage the domain. Audit first, then build.

## Produce a gap report

Write it to `<project>\.claude-context\00-ANALYSIS-AND-GAPS.md`. The shape that
works:

**1. What arrived.** A table: file name, status, notes.

| File | Status | Notes |
|---|---|---|
| About Us.docx | Complete | 6 sections, clean H1/H2 hierarchy |
| Knowledge Centre.docx | **Partially complete** | 2 of 5 articles are not usable |

Record what else came with it. One of these files had the founder's headshot
embedded in the Word document at 1240px; it would have been missed and the
client asked for it again.

**2. Each gap, with the evidence.** Not "article 1 is short" but:

> Has about 360 words of opening paragraphs. Nothing else. No H2/H3 sections at
> all, so there is no heading hierarchy to build from. No meta title, no meta
> description, no slug, while every other article has all three. No key
> takeaways, no FAQ, no conclusion. Articles 3 and 4 run 1,900 to 2,100 words.
>
> **Cannot be published as an SEO article in this state.** It would be a thin
> page and would hurt the domain rather than help it.

**3. Compare siblings.** The strongest argument is internal: four articles have
a FAQ and a conclusion, this one does not. That is measurable and hard to argue
with.

**4. Catch a promise the content does not keep.** One article's own meta
description advertised "common reporting challenges, and how companies can
build a strategic ESG reporting framework" and neither section existed. A meta
description that over-promises against the page is an SEO and UX mismatch, and
it is only visible if someone reads both.

## Say no to thin content, with a reason

Do not pad a 360-word article up to 1,500 with invented material to make it
publishable. Say it cannot ship, say exactly what is missing, and offer the two
real options: the client supplies the rest, or the page is dropped for now.

## Reserve the blocked pages

Finish the report with an appendix so nothing is silently forgotten and nothing
has to be reworked later:

| Route | Blocker |
|---|---|
| `/knowledge-centre/brsr-reporting-india-guide` | Article stops mid-way. Missing the sections its own meta description promises, plus takeaways, FAQ and conclusion. |

Reserve the slugs now, build the pages when the content lands. Also list the
plain facts still outstanding: email, phone, city, LinkedIn, legal entity name,
and any decision the client has to make.

## While building from supplied content

- **Everything on the site must be traceable to something the client supplied.**
- Keep the client's own structure, headings and tone where they read well.
- Where a design calls for something the client did not send, put a visibly
  marked placeholder, never an invention. `[CONTACT DETAILS - TO BE SUPPLIED]`
  in the footer is better than a plausible email address, because it cannot
  ship by accident.
- Note which reference sites the client named. They tell you more about what
  they want than the brief does.

## Final content audit before handover

Confirm none of these exist anywhere on the site:

- Invented statistics or counters
- Testimonials or client quotes that were not supplied
- Client logos or "trusted by" strips
- Awards or partner badges
- Team members other than the ones supplied
- Placeholder lorem ipsum left in place
- Fake email addresses or phone numbers
- Any article beyond those that were provided

If one of these is there because the design needs it, it is a question for the
client, not a gap to fill yourself.
