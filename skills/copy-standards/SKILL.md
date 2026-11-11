---
name: copy-standards
description: How client-facing words are written here — no em or en dashes, no AI filler, no invented facts, clearly marked placeholders, the two exceptions where dashes are allowed, and the correction that matters most: the failure in machine-written copy is not its vocabulary, it is that nothing is being said. Ships a checker for a document or a live page. Use whenever writing or editing any text a client or their visitors will read: page copy, blog posts, meta descriptions, emails, proposals, button labels. Triggers on "content likho", "blog likho", "copy write karo", "rewrite this", "AI jaisa lag raha hai", "slop", "human jaisa likho", "copy check karo", or any request that produces words for a client.
---

# Client-facing copy

## Everything written down is in English

Chat can be Hinglish, and usually is. **Nothing that gets saved is.**

File names, folder names, file contents, document headings, commit messages,
code comments, variable names, client replies, reports, prompt files: all
English. A Hinglish file name is unsearchable, breaks on another machine, and
cannot be handed to a client or a colleague without rewriting it.

The split is simple. Hinglish is how the work is discussed. English is what
the work leaves behind.

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
- **A dash inside code is not a dash.** Inline spans, fenced blocks and
  `<code>`, `<pre>`, `<kbd>` and `<samp>` quote literal text rather than
  punctuate a sentence, so `copy.py` blanks them before this check. A document
  has to be able to name `&mdash;` in order to forbid it, which is how this was
  found: the checker reported this rule's own wording as breaking it. A dash in
  the prose of the same document is still caught, because an exclusion that
  doubles as a hiding place has made the check worse rather than more precise.

**Two exceptions:**

1. **Verbatim client copy.** If the client supplied the text and it contains
   dashes, they stay. Note in the file that they are intentional.
2. **Legacy content.** The rule is an authoring standard for new work. It must
   not block a small fix to an article written before the rule existed. Apply it
   on create; on update, only reject a dash that the edit itself introduces.

## The word list is the easy half

This is the correction worth absorbing, and it came from reading how the
anti-slop work is actually written down.

**The failure in machine-written copy is not its vocabulary. It is that
nothing is being said.** A page can pass every rule above, carry no banned
word and no dash, and still be filler that scans as competent. Banning
"leverage" does not fix it.

So judge a draft on four things, in this order of weight:

| | The question | Weight |
|---|---|---|
| **Plain** | Can someone outside the field read it once and get it? | 30% |
| **Human** | Does it read like a person who did the work, not like a model that read about the work? | 30% |
| **Structured** | Does the shape of the page match the shape of the information? | 25% |
| **Dense** | Does every sentence carry something a reader could not have guessed? | 15% |

**Dense is the test to apply hardest**, despite carrying the least weight,
because it is the one that fails silently. Take any sentence and ask whether a
reader could have written it themselves without being told. "Our approach is
built on trust" could. "A visit costs 85 pounds and we say the price before
starting" could not. A paragraph of the first kind is what people mean when
they say something reads like AI.

### The horoscope test

The shortest version of the same question, and the one to remember:

> **Could anyone have written this, for anyone?**

If yes, it is slop. A horoscope is technically true of everyone and means
nothing to anyone, and that is exactly the register. Apply it to the whole page
first, then to the paragraph that reads worst.

The fix is never a thesaurus. It is a fact: a number, a date, a name, a
constraint, something the client told you that a competitor could not have
said.

### Two tiers, because flattening them gets the check switched off

- **Tier 1** is a tell wherever it appears in client copy: "delve", "tapestry",
  "a testament to", "unlock the power of", "seamless", "in today's fast-paced",
  "it's not just X, it's Y", "buckle up", "move the needle", "take it to the
  next level", "at the end of the day", "in a nutshell".
- **Tier 2** is a real word that machine prose reaches for far more often than
  a person does: "leverage", "utilize", "facilitate", "pivotal", "meticulous",
  "underscore", "showcase", "multifaceted", "unprecedented". **Read these in
  place rather than replacing them on sight.** Sometimes it is the right word.

Some words are deliberately in **neither** list, although the published
collections include them: bare "robust", "crucial", "comprehensive", "key".
They are correct often enough that flagging them trains people to ignore the
whole report, which is a worse outcome than the occasional "crucial".

### One structural tell worth naming

**Staccato.** Short. Punchy. Fragments. Stacked for effect. One of those lands;
four in a row is a rhythm nobody writes by accident, and it is one of the
clearest tells there is. Join them into prose.

### Where these came from

Worth knowing, because a word list with no provenance is one person's taste:

- `eugeniughelbur/clearmode` (MIT) - the four axes, the weights, and the
  per-audience numbers. Also a deterministic checker worth running on its own.
- `aplaceforallmystuff/the-antislop` (MIT) - the horoscope test, tiered
  severity, and the structural tells including staccato and uniformity.
- `jalaalrd/anti-ai-slop-writing` - the fullest vocabulary list, which cites
  the published studies behind it rather than an opinion. **No licence file**,
  so it is read and cross-checked against, not copied.

Two practical consequences:

- **Contractions read human. Keep them.** The technical-writing standards that
  ban them were written to remove ambiguity for a mechanic, not to be readable
  by a customer. "We'll call you back" is better copy than "We will call you
  back" in almost every client-facing sentence.
- **Gloss the jargon** the first time it appears, in a half-sentence, rather
  than assuming the reader is in the trade.

### The numbers, for a general audience

Taken from a standard that states them rather than implying them. These are for
a general reader; a technical audience takes 28 and 5, a social post 20 and 2.

- Sentences: **25 words maximum**
- Paragraphs: **4 sentences maximum**, broken at the topic shift
- Reading grade: **target 9, hard cap 13**
- Bold: **under 5% of the words**, one idea per section
- Three parallel items become a list. A sequence becomes numbered steps. A
  comparison becomes a table.
- Heading levels never skip. Sentence case, not Title Case.
- A long piece leads with the answer in one to three lines, then the detail.

```bash
python "C:\Claude-Code\.ai-system\skills\copy-standards\copy.py" <file-or-url>
```

It reports defects (a dash in any of its five stored forms, an exclamation
mark, an emoji, a placeholder that never got replaced), judged findings
(filler, heading skips, long paragraphs, bold everywhere), and three signals
with **no threshold** - sentence-length spread, how many sentences carry a
concrete specific, and reading grade.

**It is not a detector and cannot be one.** A person can write something that
scores badly and a model can write something clean. It measures whether a
person can read it, which is the only thing worth measuring.

It also reads only the served HTML for a URL, not the rendered page, so the
dash check still has to be repeated on the live page. For a full score across
43 rules, run clearmode (MIT, Python standard library only):
`github.com/eugeniughelbur/clearmode`. This does not reimplement it.

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
5. Pick three sentences at random and ask of each: **could the reader have
   guessed this?** If two of the three could, rewrite rather than patch.
