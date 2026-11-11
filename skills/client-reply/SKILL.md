---
name: client-reply
description: Write the reply that goes to the client. Short, plain English, no em dashes, no markdown so it pastes into email unchanged, and nothing claimed that has not been tested first. Use whenever the user asks for a reply, an update, an email or a message to a client, or says "client ko reply do", "client ko bata do", "email draft karo", "update bhejo". Always verify the claims before writing, not after.
---

# Replying to a client

## Decide it yourself. Ask only the big ones.

A reply that hands the client a wall of questions is not thoroughness, it is
the work going back unfinished. One list went out with 312 rows, 96 of them
marked "your decision", plus four more questions. The answer that came back
was the right one: if we ask the client everything, what are we developers
for.

Make the call on every item the evidence supports: their own earlier
decisions, the old site, file and folder names, duplicates already present,
rules they have already stated. Record the decision and a one-line reason.
Never write "your decision" against something you could have worked out.

Escalate only what is genuinely big or irreversible: paid content going free,
a rule of theirs that cannot be met as written. Phrase each as a short yes or
no with your default in it, so a single word answers it.

Showing the reasoning is what makes this safe. The client can overrule a
decision they can see; they cannot overrule one you never made.

## Design the question so one round ends it

When something genuinely has to be asked, the cost is not the question, it is
the round trip. A vague question comes back with a vague answer and the same
point gets raised three times, wasting their time and yours.

A question is ready to send when all four are true:

1. **It can be answered in one word or one line.** Give the options, or give
   your default and ask for a yes or no.
2. **The answer tells you what to do.** If a yes still leaves you guessing,
   the question was not specific enough yet.
3. **It carries the context they need** to answer without going to look
   something up.
4. **It is the only question**, or one of very few. A list of questions gets
   the easy ones answered and the hard ones skipped.

Bad: "How should we handle the old blog posts?"
Good: "The 31 posts from before 2024 have no traffic. I plan to redirect them
to the blog index rather than rebuild them. Shall I, or do you want any of
them kept?"

## When you are genuinely stuck

Say so early rather than guessing or stalling. Ask the person you are working
with first, since they usually know; go to the client only for what only the
client can answer. Either way, bring what you already established and the
specific thing that is blocking, not the whole problem.

The user pastes what you write straight into email. It has to arrive looking
exactly as written, say only things that are true, and be short enough to read
on a phone.

## Verify first, write second

**Before a single line is written, test every claim the reply will make.** Not
after, not "I'll check if you want". The reply is the last step.

- "The form is working" means you submitted a test and confirmed it arrived.
- "The page is live" means you loaded it and read the status code.
- "It is fixed" means you reproduced the fault first and then saw it gone.
- "Nothing else changed" means you diffed it.

If something could not be tested, the reply says so plainly. A sentence like
"I have not been able to confirm X yet, and here is what I need to" is a good
reply. A confident guess is how an account is lost.

Never promise an outcome. Commit to the diagnosis and the method, never to the
result, until the data is in hand.

## Format: it must survive the paste

**Write plain text. No markdown at all.** No `**bold**`, no `#` headings, no
`-` bullet characters, no backticks, no tables. Those paste into Gmail and
Outlook as literal asterisks and hashes and make the agency look careless.

Structure comes from short paragraphs and blank lines, not from symbols.

Where a list is genuinely needed, number it as plain text:

```
1. Forward me the bounce message from your webmail.

2. Create a mailbox for the website to send through, for example
   website@example.com, and send me the password.
```

**No em dashes and no en dashes.** Commas, full stops, colons or a rewritten
sentence instead. Check before handing it over, including for the entity
`&#8212;`.

Deliver it two ways so it can be copied in one action:

1. Write it to `<project>\.claude-context\replies\<date>-<topic>.txt`
2. Show it in the chat inside a plain fenced block, with nothing above or below
   the block except one short line saying what it is

## Shape of the reply

```
Subject: <plain statement of the point, no hype>

Hi <first name>,

<one line that frames it: what this is about>

<Label sentence.> <The explanation in plain English.>

<Label sentence.> <The explanation.>

<What happens next, or what you need from them.>

Best,
```

- Open with one line that tells them what the message is about.
- One topic per paragraph. Start the paragraph with a short label sentence so
  the eye can scan it, then explain.
- End with the next step, a question, or the specific thing you need.
- "Best," on its own line. No signature block, the user adds their own.
- 150 to 400 words. If it is longer, something belongs on a call instead.

## Tone

Plain English. Short sentences. Explain the thing, not the technology.

> "It is set to load only when a visitor scrolls down to it, which keeps the
> rest of the page fast."

That is lazy loading explained without the words "lazy loading". Do that.

- No jargon, no hype, no exclamation marks, no emoji.
- British or American spelling, consistently, matching the client.
- Say "I" and "you". Not "we have actioned your request".

### The email phrases that mark a reply as unread-and-automated

These are the ones clients see most often and recognise fastest, because every
other automated mail they get opens the same way. They cost nothing to remove
and the sentence is always better without them:

| Never | Instead |
|---|---|
| "I hope this email finds you well" | Open with the thing. "The form is fixed." |
| "Please don't hesitate to reach out" | "Reply here if anything looks wrong." |
| "As per my last email" | "On Tuesday I mentioned..." It reads as a reprimand. |
| "Just following up" / "touching base" / "circling back" | "Checking whether you got the staging link." |
| "Thank you for your patience" | Only if they actually waited, and then say how long. |
| "Rest assured" | Say the thing that provides the assurance. |
| "Certainly," / "Absolutely," / "Great question!" | Delete. Start with the answer. |
| "Apologies for the inconvenience" | Say what went wrong and what you did. |

Two more that look polite and are not: **"Let me know if you have any
questions"** at the end of a message that raised none, and **"I wanted to reach
out"**, which spends a sentence announcing that a message is a message.

`copy-standards` has the full picture and a checker. This table is the subset
that shows up in client mail.

## Things that build trust, from replies that worked

**Admit a miss directly.** "You were right, and I had missed it." Then say what
was done about it.

**Say what you did not do, and why.** "Those two cannot be removed without
putting your SMS messaging at risk, so I have left them exactly as they were."
This matters more than the list of what you did.

**Separate a fault from a setting.** "That is the speed setting doing its job
rather than a fault." Clients often report a non-fault; say so kindly.

**Give evidence, briefly.** "I submitted two test enquiries today and both were
captured correctly." One clause, not a paragraph.

**When asking for something, say why.** "I would suggest creating a new mailbox
rather than using yours, so your own password stays private."

**Offer options with a recommendation.** Give A and B, say which you recommend
and in one line why. Never hand over an open question with no view.

**Give a time estimate when you can.** "Once I have either of those, this is
about fifteen minutes of work."

**If the estimate is one the client will hold us to, record it before sending.**
A figure agreed in a reply or on a call is the one nobody can reconstruct
later:

```bash
python "C:\Claude-Code\.context-system\worklog\estimate.py" record "<project>" \
    --hours 40 --for "migration" --dated YYYY-MM-DD --source "agreed on the 2 Nov call"
```

Not for "about fifteen minutes". For anything that becomes a commitment.

**Never put a password, key or token in the reply.** Ask them to send it, or
point at where it lives.

## Before handing it over

1. Every claim in it was tested, and you can say how
2. No em dash, no en dash, as characters or entities
3. No markdown symbols anywhere
4. Under 400 words
5. Read once as the client: does it answer what they asked, and is the next
   step obvious
