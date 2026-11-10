---
name: forms-and-leads
description: Make a form actually deliver a lead, check that the analytics tags actually fire once and without the lead's data in them, and keep that data out of the places it must never go. Covers the silent-failure traps (dead nonces, expired reCAPTCHA tokens, synthetic clicks), what a real test submission proves, BCC and recipient rules, and the hard privacy line on pixels and AI services. Use whenever building, moving, fixing or testing any form, or when leads stop arriving. Triggers on "form", "lead", "enquiry", "contact form", "form kaam nahi kar raha", "leads nahi aa rahe", "submission", "analytics", "GA4", "GTM", "tag fire ho raha hai", "conversion track", "pixel", "reports khali hain".
---

# Forms and leads

## When leads stop, check the form still exists

On one set of landing pages the lead endpoint, its validation, its database
table and its email were all intact and working. Thirteen leads arrived over
three weeks, then zero for two months. Nothing had broken: the forms had been
replaced with links to an off-site "schedule a call" page during a CTA tidy-up,
and one page ended up with seventeen of them.

The leftovers were visible in the code the whole time - a component still
named for a form that rendered only a link, and a prop nothing read.

So when conversions go to zero, before debugging delivery: open the page and
confirm there is still a form on it. A working endpoint that nothing calls
looks exactly like a working system from the server side.

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

## Check the tags, because that is the number the client reads

Delivery is half of it. The other half is whether the client's reports show
what happened, and a tag in the source is not a tag that fired.

```bash
node "C:\Claude-Code\.ai-system\skills\forms-and-leads\analytics.js" <url> \
  --out <project>\.claude-context\qa\analytics --consent
```

It watches the network rather than reading the markup, because the markup says
what was intended and the network says what happened. What it finds:

- **A tag declared and silent.** A GA4 id sitting in the page with no hit ever
  reaching the collector. The page looks correctly tagged and the reports are
  empty.
- **A page view counted more than once.** Two `page_view` hits to the same
  measurement id for one load, which is almost always the tag hardcoded in the
  page *and* the same tag again inside Tag Manager. Worse than no tag: every
  number the client reads is inflated and every decision off it is wrong.
- **Consent that defaults to denied and is never granted.** `analytics_storage`
  starts denied, nothing calls consent update, and the client sees almost no
  users while the banner looks like it works.
- **The lead's own data leaving.** This is the privacy rule above, made
  checkable: an email or a phone number in a pixel request, parameters named
  `em`, `ph`, `fn`, and a sha256 hash, which is how advanced matching sends a
  customer's email. Hashed is not plaintext and it is still their data going to
  an ads platform.

`--click "<selector>"` fires one interaction and reports what was sent, which
is how you check a conversion actually registers. **Only on a page you have
been told you may exercise** - never fire a real submission on a live client
form to test a tag.

`--consent` clicks the cookie banner's accept button, because most tags
deliberately send nothing until it is answered and "no hits" is otherwise the
wrong conclusion. **It is an opt-in flag for a site you have been asked to
audit, in a throwaway browser, and nowhere else.** Accepting a consent banner
is a decision on somebody's behalf: do not pass it while signed in as anyone,
on a page that also accepts terms, or on a site that is not the client's. The
default is to observe and report that consent was never answered.

Two honest limits, which the report states: it is one load on one machine with
no ad blocker, so a real visitor's blocker stops some of this and the client's
own numbers will always be lower; and it checks that a hit was *sent*, not that
the property received it. For that, open the property.

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
