---
name: site-recon
description: Work out everything about a client's existing website before touching it — registrar, who really owns the domain, which DNS zone is actually being served, hosting, CMS and stack, email records, TLS, analytics IDs, brand assets, phone and email — then say plainly what still has to come from the client. Use at the start of any new client, before any migration, go-live, DNS change or domain transfer, and whenever "the site is down" or "leads stopped". Triggers on "new client", "client ki website", "domain kahan hai", "DNS", "hosting", "migration", "go live", "site down", "kaun si CMS hai", "what do we need from the client".
---

# Site recon

Before anything is changed, know what is actually there. Most of the expensive
mistakes on these projects came from acting on what a control panel claimed
rather than on what the internet was actually serving.

## Run it

```bash
python "C:\Claude-Code\.ai-system\skills\site-recon\recon.py" <domain> --out <project>\.claude-context\recon
```

It writes `recon.md` and `recon.json`. Nothing it does needs a login.

It asks **two independent resolvers** (Google and Cloudflare) for every DNS
answer and flags any disagreement, because that disagreement is the single most
useful signal there is.

## What it finds, and why each one matters

| Finding | Why it matters |
|---|---|
| Registrar, registrant, expiry, lock status, auth code availability | A domain registered in the agency's name is not the client's. One client was told the account was his while the registrant of record was the previous agency. |
| Registry nameservers vs live NS answer | A hosting panel can show a full DNS zone that is **dormant**. Edits there change nothing until the registry delegation moves. Compare the two before editing anything. |
| MX, SPF, DMARC, DKIM selectors | The client's mail dies if these do not survive a zone change. More than one SPF record breaks mail outright. |
| Verification TXT records (`_lovable`, `_lovable-email`, site verifications) | These are the records people forget in a zone migration, and the platform then de-verifies the domain. One migration to Cloudflare dropped them and the site returned HTTP 421. |
| Cloudflare proxy (orange cloud) | Hides the real origin and breaks domain binding on Lovable and Vercel-style hosts. |
| IP, reverse DNS | Names the real host, which the panel often does not. |
| TLS issuer, SANs, days to expiry | A certificate on a different domain name tells you where the site really lives. |
| Platform / CMS, framework, analytics IDs | Decides what can and cannot be built, and which skills apply. |
| Title, H1, meta, favicon, logo, OG image, phone, email | The brand facts to carry into a rebuild, and where a staging URL has leaked into production. |
| robots.txt, sitemap.xml and its URL count | The page inventory for a migration. |

## Read the output properly

The tool reports; the judgement is yours.

1. **If the resolvers disagree, stop and find out why** before changing
   anything. That is a split-brain zone.
2. **If registry NS and the panel's zone differ**, say which one is live and
   which one is decorative. Never edit the decorative one and report success.
3. **Write down the MX and SPF before any change**, and check them again after.
   This is the one that loses a client.
4. **A 403 or a block is not "the site is down."** Cloudflare has blocked this
   office IP while serving Googlebot normally. Check from another vantage point
   before telling anyone the site is offline.
5. Do not put credentials in the report, in chat, or in a memory file. Record
   *where* a credential lives, never the value.

## After the automated pass

Open the site and look at it, at phone and desktop width. The tool reads
headers and HTML; it cannot tell you the site is ugly, the content is thin, or
half the pages are placeholders. Run `responsive-qa` on the home page and one
inner page while you are there.

Then write the findings into the project's memory so the next session, on any
account, starts from facts instead of asking the client again.

## What to ask the client — and what not to

Ask only for what genuinely cannot be found. Asking for things already
discovered makes the agency look careless.

**Access (ask for these):**
- Registrar login, or the auth/EPP code with the domain unlocked
- The DNS panel that is actually authoritative
- CMS admin, plus SFTP or Git
- Who hosts the mailboxes and who administers them
- Analytics, Search Console, Tag Manager, Ads

**Assets and facts (ask for these):**
- Logo source files, brand colours and fonts, and licences for any stock imagery
- Legal entity name, registered address, phone, licence or registration numbers
- Anything a visitor is told that must be true: certifications, awards, review
  counts, years in business

**Decisions (ask for these):**
- Which URLs must keep working and which may be retired
- What must never be touched
- Who signs off, and who must not be surprised by a change

**Do not ask for:** the registrar, nameservers, MX, hosting IP, CMS, analytics
IDs, sitemap or page list. Those are in the report already.

## Hand it to the main agent as

- **Facts** — verified, with how each was checked
- **Risks** — what will break, and what must survive a change
- **Blocked on the client** — the short list above, nothing more
