---
name: client-reply
description: Write the reply that goes to the client — short, plain English, no em dashes, no markdown so it pastes into email unchanged, and nothing claimed that has not been tested first. Use whenever the user asks for a reply, an update, an email or a message to a client, or says "client ko reply do", "client ko bata do", "email draft karo", "update bhejo". Always verify the claims before writing, not after.
---

# Replying to a client

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

## Format — it must survive the paste

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

**Never put a password, key or token in the reply.** Ask them to send it, or
point at where it lives.

## Before handing it over

1. Every claim in it was tested, and you can say how
2. No em dash, no en dash, as characters or entities
3. No markdown symbols anywhere
4. Under 400 words
5. Read once as the client: does it answer what they asked, and is the next
   step obvious
