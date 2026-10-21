---
name: copy-standards
description: How client-facing words are written here — no em or en dashes, no AI filler, no invented facts, clearly marked placeholders, and the two exceptions where dashes are allowed. Use whenever writing or editing any text a client or their visitors will read: page copy, blog posts, meta descriptions, emails, proposals, button labels. Triggers on "content likho", "blog likho", "copy write karo", "rewrite this", "AI jaisa lag raha hai", or any request that produces words for a client.
---

# Client-facing copy

A client once called a mockup "designed by AI" and the project was nearly lost.
Everything here protects against that.

## Punctuation — the AI tell

**No em dash (—, `&#8212;`, U+2014). No en dash (–, `&#8211;`).** Anywhere in
copy. This has been asked for on 12 separate projects.

Replace with a comma, a colon, a full stop, parentheses, or a rewritten
sentence. A spaced hyphen ` - ` is its own tell; prefer restructuring.

**Finding them is the hard part:**

- They are often stored as the entity `&#8212;` or `&mdash;`, so searching for
  the literal character finds nothing. Search for the character **and** the
  entities, in the database as well as the source.
- Check rendered output too, not only source — a renderer can introduce them.
- `→` is allowed. It is an arrow, not a dash.

**Two exceptions:**

1. **Verbatim client copy.** If the client supplied the text and it contains
   dashes, they stay. Note in the file that they are intentional.
2. **Legacy content.** The rule is an authoring standard for new work. It must
   not block a small fix to an article written before the rule existed. Apply it
   on create; on update, only reject a dash that the edit itself introduces.

## Voice

Calm, specific, second person, short sentences.

Never: exclamation marks, hype, emoji in body copy, or the filler vocabulary —
"unlock", "dive in", "game-changer", "supercharge", "elevate", "seamless",
"in today's fast-paced world", "it's not just X, it's Y".

Match the tone that is already on the site. If the existing pages read well,
keep their structure, headings and plain-English register; change only what was
asked.

## Never invent a fact

This is the rule that saves accounts. Do not invent:

- company history, founding dates, locations, registration or licence numbers
- credentials, certifications, employer names, years of experience
- review counts, ratings, awards, client names
- market figures — rental yields, capital growth, occupancy, population,
  transaction volumes
- listings, products, services or team members that do not exist

If a fact is needed and not supplied, write a **clearly marked placeholder** and
ask. `[AUTHORNAME]` as a literal placeholder everywhere is better than a
plausible name, because it can be replaced in one pass and is impossible to ship
by accident.

When a page is a layout task with placeholder text, it stays placeholder text.
Do not invent sections, reorder them, or "improve" the layout.

## Migrating or rewriting existing copy

- Migrate exactly what is there. Do not invent, drop or reorder.
- Keep the meaning and the tone when restructuring a sentence to remove a dash.
- When content moves to a new page, put each line back in that page's own voice
  and components.

## Images in content

Photography should look real: ordinary people, real settings. Avoid clinical
stock, avoid anything that reads as AI-rendered, avoid pitying or dramatised
imagery on sensitive topics. Every image needs meaningful alt text.

Mark any image that is a stand-in as a placeholder, visibly, so it cannot ship.

## Before handing copy over

1. Searched for em dash and en dash, as characters and as entities, in source
   and in rendered output
2. No exclamation marks, no emoji, no filler vocabulary
3. Every number, date, name and credential is either sourced or a marked
   placeholder
4. Read it out loud once. If it sounds like a brochure written by nobody, it is
   not finished.
