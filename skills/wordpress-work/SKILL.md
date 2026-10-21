---
name: wordpress-work
description: Working safely on a client's WordPress site — pull before you upload, the saves that silently do not save, the caches that hide your change, the dash WordPress rewrites behind your back, Elementor and ACF traps, and why site mail lands in spam. Use before touching any WordPress site, admin setting, theme file, Elementor page or form. Triggers on "wordpress", "wp-admin", "elementor", "kadence", "astra", "acf", "wpforms", "gravity forms", "plugin", "theme", "wp site me change".
---

# Working on a WordPress site

Every rule here comes from something that actually broke on a client site.

## Getting in, and what you do first

The user signs in themselves, on their own browser profile, and hands you the
session. You never create an account, reset a password, or type a credential.

Once you are in, the work does not start with the change. It starts with
looking, and the order is not optional:

1. **Open everything the task touches.** Not the one screen you think you need.
   The page in the admin, the page as a visitor sees it, the template that
   renders it, the plugin that owns it, the theme settings it inherits from,
   and anything else that writes to the same field. A meta title can come from
   the post, from Yoast, from the theme, or from a filter in `functions.php`,
   and only one of them is winning.
2. **Skip nothing because it looks irrelevant.** The setting you did not open
   is the one that overrides you.
3. **Assume nothing.** If you cannot see where a value comes from, go and find
   it. Do not reason from how another site was built, from the plugin's usual
   behaviour, or from what the screen seems to imply. On a live install your
   guess is someone else's broken page.
4. **Say what you found and what you are about to change**, including the blast
   radius, before you change it.
5. **Then implement**, the way a developer would: the smallest change that
   does the job, in the right place, not a workaround pasted somewhere easier.
6. **Then test and verify it yourself.** Reload with the cache bypassed, read
   the saved value back, and look at the live page. A green save notice is not
   verification. See `verify-before-claiming`.

## Before you touch anything

**Assume the server is the source of truth, not your copy.** On one site the
client edits theme files directly on staging. A local repo goes stale within
hours, and an SFTP upload silently overwrites whatever he changed. One
`functions.php` upload destroyed two of his own speed fixes from that morning.
WP Engine SFTP keeps no file history and `_wpeprivate` holds no backup.

So: **pull the live file, diff it against your copy, and only then upload.** If
you cannot pull, capture the rendered HTML before the change, which is the only
reason those two fixes were recoverable.

**Find out who else is in the install.** One site had another agency's
developer making live changes the same week, plus the client and the previous
agency's email still on the admin account. Check Users, check recent revisions,
and coordinate before editing.

**Confirm the mandate.** "Understand it fully first, make no edits until told
otherwise" is a real instruction that was given on a real takeover. Read the
project's memory before assuming you may change anything.

## The saves that do not save

| Trap | What you see | What to do |
|---|---|---|
| JavaScript `element.click()` on a Vue toggle (AIOSEO) | The on-screen text changes, so it looks like it worked. The component never commits, and Save posts the old value. | Use a real browser click on a marked selector, never a synthetic one. |
| WPCode's Update button silently no-ops | Nothing happens, no error | Re-open the snippet and confirm the stored value changed |
| `_elementor_data` written over REST | Structure, classes and IDs render. Styling added in that save is silently missing, because `post-<id>.css` is never regenerated. | Put page-specific CSS in an `html` widget inside the page, targeting `_element_id` and `.elementor-element-<id>`. |
| `_css_classes` on a section | Renders on widgets, not on sections | Target the element ID instead |

**After every admin save, reload the page and read the value back.** A save is
not done because the UI said so.

## The cache that hides your work

A change can be correct in the database and invisible to Google, Ahrefs and
visitors.

- With NitroPack, verify using `?nonitro=1`. **Not** `?cb=` — that does not
  bypass it.
- Purge **the current page**, not the entire cache, on a site with paid
  traffic. One full purge rebuilt about 966 pages.
- Check the front end logged out, in a private window. A logged-in view often
  bypasses cache and lies to you.

## The dash WordPress inserts behind your back

`wptexturize` silently turns a spaced hyphen ` - ` into an **en dash** in
anything that runs through the content filters: Elementor text widgets, FAQ
answers, icon-list items. Headings keep the plain character, so it looks
inconsistent and random.

Write `&#45;` instead. It survives and renders as a real hyphen.

This matters because the house rule is no em or en dashes anywhere. See
`copy-standards`. Searching for the character in the editor will not find these
— check the rendered page.

## Forms

See `forms-and-leads` for the full set. The WordPress-specific ones:

- **WPForms markup pasted as static HTML has a dead nonce.** Submissions
  silently vanish. Always use the real shortcode or block.
- Elementor's Bcc works; if one recipient sees nothing, suspect that address,
  not the form.
- Test by actually submitting and confirming the entry and the email arrived.

## Mail almost certainly lands in spam

On one site every mail WordPress sent as the client's own domain failed SPF:
the domain publishes `-all` and authorises only their real senders, while the
site runs on a different host with a bare `googleusercontent.com` reverse DNS.

- Changing the From address is **not** a workaround — another domain will not
  authorise that server either.
- The fix is an SMTP sender the domain already trusts. If `include:sendgrid.net`
  is already in their SPF, that is the shortest path.
- That needs an API key or mail credentials **from the client**. Do not handle
  the credential value; ask them to enter it.

## Where the data actually lives

Before editing a page, find out where its content comes from. On one install,
every practice NAP and booking link lived as ACF fields on a single taxonomy
term, reaching pages through a shortcode registered in a WPCode snippet.
Changing one field there changed every "Book Now" button on the site.

Look for: ACF field groups, a child theme's `functions.php`, WPCode or Code
Snippets entries, Elementor Theme Builder templates and their display
conditions, and any page builder's global widgets.

## Styling and CSS

- **Child theme only.** Never edit the parent; an update erases it.
- If there is no child theme, say so before adding CSS anywhere.
- No npm. For motion, use an IntersectionObserver with CSS transitions rather
  than a bundled library.

## Before saying it is done

1. Pulled the live file and diffed before uploading
2. Re-opened every admin setting and read the value back
3. Checked the front end logged out, with cache bypassed
4. Searched the rendered page for en dashes, not just the editor
5. Submitted a real test through any form touched, and confirmed it arrived
6. Ran `responsive-qa` on the pages changed
