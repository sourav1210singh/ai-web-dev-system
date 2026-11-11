---
name: forms-and-leads
description: Make a form actually deliver a lead, check that the analytics tags actually fire once and without the lead's data in them, and check the mail can authenticate at all, and keep that data out of the places it must never go. Covers the silent-failure traps (dead nonces, expired reCAPTCHA tokens, synthetic clicks), what a real test submission proves, BCC and recipient rules, and the hard privacy line on pixels and AI services. Use whenever building, moving, fixing or testing any form, or when leads stop arriving. Triggers on "form", "lead", "enquiry", "contact form", "form kaam nahi kar raha", "leads nahi aa rahe", "submission", "analytics", "GA4", "GTM", "tag fire ho raha hai", "conversion track", "pixel", "reports khali hain", "mail spam me ja rahi hai", "email nahi pahunch rahi", "SPF", "DKIM", "DMARC", "deliverability".
---

# Forms and leads

## When leads stop, check the form still exists

On one set of landing pages the lead endpoint, its validation, its database
table and its email were all intact and working. Thirteen leads arrived over
three weeks, then zero for two months. Nothing had broken: the forms had been
replaced with links to an off-site "schedule a call" page during a CTA tidy-up,
and one page ended up with seventeen of them.

The leftovers were visible in the code the whole time. A component still
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
| WPForms markup pasted as static HTML, the nonce is dead | WordPress landing pages | Form submits, success shows, nothing is stored. Leads vanish for weeks. |
| reCAPTCHA token expires before submit | any | "Error trying to send your message", intermittent, worse on slow fills |
| Synthetic JS clicks in the WP admin | WordPress settings | The setting looks saved and is not. Always save through the real UI and reload to confirm. |
| A page rebuilt without its form | landing pages | The old page had a working lead form; the new one looks better and captures nothing. |
| SFTP upload reporting success on a DNS failure | file deploys | `-w` prints "uploaded". Verify by checksum, never by the tool's own word. |
| Email sent but undelivered | any | SPF, DKIM or a missing DMARC alignment. Check the destination, not the send log. See below, most of this is now measurable. |

## Will the mail authenticate at all

```bash
python "C:\Claude-Code\.ai-system\skills\forms-and-leads\mail.py" <domain> \
  --out <project>\.claude-context\qa\mail
```

`site-recon` records MX, SPF, DMARC and the DKIM selectors. Recording them is
not judging them, and the faults that matter all look fine in a DNS panel.

**The one worth knowing about: SPF has a hard limit of ten DNS-querying terms.**
RFC 7208 section 4.6.4 names them - `include`, `a`, `mx`, `ptr`, `exists` and
the `redirect` modifier, and requires a receiver to return **permerror** past
ten, which means SPF fails for every message the domain sends. `ip4`, `ip6` and
`all` cost nothing.

It is reached by adding one more sending service. A record reading

```
v=spf1 include:a include:b include:c mx a -all
```

shows five terms and can be fourteen once the includes are followed, because
each include brings its own. **Nothing anywhere reports this.** The panel is
tidy, the record is present, and authentication is simply off. `mail.py` counts
it recursively and prints the chain so the cost of each include is visible.
Large senders flatten their records into `ip4` blocks for exactly this reason.

The rest of what it checks:

| Finding | Why it is what it is |
|---|---|
| Two SPF records | A blocker. Not "the first one wins": two records is a permerror and SPF fails entirely. Merge them. |
| `+all` | A blocker, and worse than no SPF: it explicitly authorises every sender on the internet. |
| `?all`, or no `all` at all | Asserts nothing. `~all` while a change beds in, `-all` once the sender list is known to be complete. |
| No MX | A blocker if the client reads mail here. If mail lives elsewhere on purpose, record that so nobody "fixes" it. |
| `p=none` in DMARC | Monitoring with no enforcement. The right first step and the wrong permanent state, and where most domains sit for years believing they are protected. Reported, does not hold a launch. |
| No `rua` | Nobody receives the reports, so nobody can see which senders fail before enforcing. |
| An empty `p=` on a DKIM selector | The key is revoked; anything signed with it fails. |
| `ptr` | RFC 7208 marks it "do not use". |

Two honest limits, which the report states:

- **Coherent records are necessary, not sufficient.** They do not prove a
  message arrived. Reputation, content and the receiving server decide too.
- **Only the common DKIM selector names are tried.** No selector found means
  none of those names resolved, not that there is no DKIM. Confirm with the
  sending service.

So this does not replace the rule at the top of this skill. **Send a real test
and confirm it in the destination inbox,** the inbox, not the send log, and
look in the spam folder before calling it delivered.

`fix-job` runs it on **golive**, **watch** and **drop**: a bad domain move kills
search and mail together, and the SPF lookup count creeping towards ten is
exactly what a weekly run should catch before it crosses.

## Privacy: the hard line

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

It also inventories **what could convert on the page against what is set up to
notice it**. Checking which tags fire answers half the question; the other half
is what should fire. A site can have a clean analytics report while the phone
number, the WhatsApp button, the booking link and the chat widget go
unrecorded, so "conversions" means the forms only and the number is wrong in a
direction nobody questions.

What counts as a conversion action: `tel:`, `wa.me`, `mailto:`, forms, add to
cart, a booking link, a popup or CTA trigger, a file download, a chat widget, a
video. A page load cannot tell you which of them fire, because they fire on
click, so the report lists them and says so rather than implying they are
tracked.

## AJAX forms need their own success signal

This is the tracking equivalent of the dead-nonce trap above, and it is the
most common reason a form "has tracking" and reports nothing.

**A form that submits without a page load cannot use a native Form Submission
trigger.** The trigger either never fires, or fires on a submit that failed
validation, which is worse, because the number looks healthy.

| Plugin | What to listen for |
|---|---|
| Elementor | a MutationObserver on `.elementor-message-success` |
| Contact Form 7 | the `wpcf7mailsent` event |
| WPForms | the `wpformsAjaxSubmitSuccess` event |
| Gravity Forms | the `gform_confirmation_loaded` event |
| Ninja Forms | its native `nfFormSubmitResponse` dataLayer event |
| HubSpot | the `message` event with `type: "hsFormCallback"` |
| Calendly | the `calendly.event_scheduled` message event |

Each one pushes a `dataLayer` event, and the tag fires on that custom event
rather than on a form submission. `analytics.js` reports a plugin it finds with
no matching listener anywhere on the page: **check the container before
concluding it is missing**, because a listener installed through a GTM custom
HTML tag is injected at runtime.

A plain HTML form that reloads or redirects to a thank-you page is fine with a
native trigger, or with a pageview trigger on the thank-you URL.

## Event names, so two sites can be compared

Use GA4's own recommended names where one exists, because the standard ones get
reporting Google builds for them. `generate_lead` for a lead form, not
`form_submit_contact_v2`.

| Action | Event |
|---|---|
| Form submit (lead) | `generate_lead` |
| Phone click | `phone_call` |
| WhatsApp click | `whatsapp_click` |
| Email click | `email_click` |
| CTA click / popup | `cta_click`, `popup_open` |
| Add to cart, checkout, purchase | `add_to_cart`, `begin_checkout`, `purchase` |
| Chat opened | `chat_initiated` |
| Video | `video_start`, `video_progress`, `video_complete` |
| File download | `file_download` |
| Appointment booked | `appointment_booked` |

## Audit before you add

Read the container's existing tags and triggers first, and inspect the site
before deciding what needs tracking. Do not assume the list. Duplicate tracking
is not a smaller problem than no tracking. It inflates every number, which is
the one failure that survives review because the graph still looks right.

Two platform traps worth knowing before promising a client anything:

- **Shopify blocks GTM on `/checkout`.** Purchase tracking there goes through
  Shopify's own Customer Events or Web Pixels, not a GTM tag.
- **Wix needs a paid plan to inject head code**; Squarespace allows code
  injection. Check which before scoping the work.

`--click "<selector>"` fires one interaction and reports what was sent, which
is how you check a conversion actually registers. **Only on a page you have
been told you may exercise.** Never fire a real submission on a live client
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
3. Submit a test and follow it through every hop: handler, database, email,
   CRM. Find the hop where it disappears.
4. Only then look at the form markup.

Report the hop where it fails, with the evidence, before proposing a fix.
