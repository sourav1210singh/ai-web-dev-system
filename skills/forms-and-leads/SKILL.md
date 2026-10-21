---
name: forms-and-leads
description: Make a form actually deliver a lead, and keep the lead's personal data out of the places it must never go. Covers the silent-failure traps (dead nonces, expired reCAPTCHA tokens, synthetic clicks), what a real test submission proves, BCC and recipient rules, and the hard privacy line on pixels and AI services. Use whenever building, moving, fixing or testing any form, or when leads stop arriving. Triggers on "form", "lead", "enquiry", "contact form", "form kaam nahi kar raha", "leads nahi aa rahe", "submission".
---

# Forms and leads

Forms are the most broken thing on these projects: 396 mentions across 18 of
them. They break silently, which is why they stay broken.

## A form is not working until a real submission arrives

Seeing a success message proves nothing. The success state is rendered by the
front end and will happily appear when the back end received nothing.

**Submit a real test and then confirm it arrived** in whichever of these the
project uses:

- the row in the database
- the email in the recipient's inbox (and the BCC inbox)
- the entry in the CRM
- the entry in the WordPress admin

Say which one you checked. If you could not check the destination, say that
instead of saying the form works.

## The silent-failure traps, all of them real here

| Trap | Where | How it looks |
|---|---|---|
| WPForms markup pasted as static HTML — the nonce is dead | WordPress landing pages | Form submits, success shows, nothing is stored. Leads vanish for weeks. |
| reCAPTCHA token expires before submit | any | "Error trying to send your message", intermittent, worse on slow fills |
| Synthetic JS clicks in the WP admin | WordPress settings | The setting looks saved and is not. Always save through the real UI and reload to confirm. |
| A page rebuilt without its form | landing pages | The old page had a working lead form; the new one looks better and captures nothing. |
| SFTP upload reporting success on a DNS failure | file deploys | `-w` prints "uploaded". Verify by checksum, never by the tool's own word. |
| Email sent but undelivered | any | SPF, DKIM or a missing DMARC alignment. Check the destination, not the send log. |

## Privacy — the hard line

A lead's personal data goes to the systems the client agreed to, and nowhere
else.

- **Never send form field values to an analytics or ads pixel.** Send the event
  name and nothing else. No name, email, phone, message, budget or any other
  field.
- **Never send enquiry field values to an AI service.** Not for classification,
  not for summarising, not "just to tidy it up".
- **Fire pixels client-side only.** Do not fire them from the server-side
  enquiry handler.
- On a form that crosses borders, the privacy text needs a **named recipient**
  and a cross-border transfer line.
- Never log full field values where logs are broadly readable.

## Recipients and routing

- Do not change the recipient, the BCC or the reply-to unless that is the task.
  These are set deliberately and a change silently redirects the client's leads.
- Keep a BCC to the agency address exactly as configured.
- A lead with no name cannot be followed up. Keep Name required even when the
  client only marked Email as mandatory, unless they explicitly refuse.
- Do not add fields the client removed.

## Building the form itself

- Labels bound to inputs, correct `type` and `autocomplete`, inline validation
  messages next to the field that failed, and no submit on an invalid form.
- A real success state that replaces the fields, not just a toast.
- 44x44 minimum tap targets and no `required` field that cannot be completed on
  a phone.
- Phone validation that accepts the formats the client's country actually uses.
- Keep the existing field order, layout and thank-you state when the task is
  about something else.

## When leads stop arriving

Work outward from the destination, not inward from the form:

1. Is anything arriving at the destination at all, from any source?
2. Did a deploy, plugin update or page rebuild land near the date it stopped?
   Check the site's own change log.
3. Submit a test and follow it through every hop — handler, database, email,
   CRM — and find the hop where it disappears.
4. Only then look at the form markup.

Report the hop where it fails, with the evidence, before proposing a fix.
