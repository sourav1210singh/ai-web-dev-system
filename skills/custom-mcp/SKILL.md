---
name: custom-mcp
description: How the per-site MCP servers in this workspace are built, secured, connected and kept honest — the hosted HTTP endpoint pattern, secret handling, server-side validators, and why the server's own instructions have to be re-checked against the live site. Use when building a new MCP for a client site, changing an existing one, connecting one to Claude, or when an MCP's tools behave unexpectedly. Triggers on "mcp banao", "new mcp", "mcp connect", "mcp server", "blog publishing", "edge function", "mcp tool".
---

# Building a per-site MCP

Half a dozen of these already exist in this workspace, one per client site.
They are the same server with different credentials, so build the next one the
same way rather than inventing a new shape.

## The pattern that works

**Host the MCP inside the site itself**, not as a local process. Two proven
forms:

1. **An app route** — `https://<site>/api/public/mcp?secret=<key>`, a route in
   the Lovable/TanStack app, sharing its validation with the REST endpoint.
2. **A Supabase edge function** —
   `https://<ref>.supabase.co/functions/v1/mcp`, MCP JSON-RPC, stateless, so
   `tools/list` works without a session.

Connecting it needs no install and no Node on the machine:

```bash
claude mcp add --transport http <name> "<url with ?secret=>"
```

A local Node stdio server is the fallback, not the default. One was written and
never tested because the main PC had no Node; the hosted URL superseded it.

## Auth

- Header `X-MCP-Secret: <secret>` is the primary. Some also accept `?secret=`
  and `Bearer`, which is what makes the claude.ai connector form possible.
- Verify the negative cases, not just the happy path: wrong secret must 401,
  `GET` must 405, a notification must 202.
- Secrets live in a `.env.<name>` file in the project folder. **Never in chat,
  never in a memory file, never in the log.** Record where the value lives.
- Rotate on exposure and note the date the old one was revoked.

## Put the format inside the tool descriptions

The tool descriptions should carry the full data format, so a fresh Claude on
any account needs no extra briefing. That is what makes these usable after an
account switch.

## Validators reject, they do not auto-fix

Server-side validation is where the house rules become enforceable. The ones
already in use:

- em dashes, en dashes, `--` anywhere, standalone `---` lines
- duplicate slug
- internal link count outside the allowed range
- HTML entities in plain-text fields

Reject with a clear message rather than silently correcting, so the caller
learns the rule. But think about which path each rule belongs on: a link-count
rule that is right for new content punishes a small fix to an article written
before the rule existed. Put authoring standards on create, and on update only
reject what the edit itself introduces.

## The trap that cost the most

**An MCP's own embedded instructions can be wrong.** One server's editorial
template told Claude to write a Quick Answer / TOC / Key Takeaways / FAQ
markdown structure. The live site renders raw HTML through
`dangerouslySetInnerHTML`, so markdown would have displayed as literal text,
and the client had already rejected that format.

So:

- **Re-check the server instructions against what the site actually renders**,
  and correct them when they drift. They are the only thing telling a fresh
  Claude what is safe.
- Read one live post before writing a new one. The rendered page is the spec.
- Find out what the template renders **for** you — breadcrumb, H1, byline, read
  time, TOC sidebar, author card, CTA, related posts, JSON-LD. Sending those in
  the body duplicates them.
- Watch for a renderer that adds things: one site had a keyword auto-linker
  that turned an authored 3-4 internal links into 10 or more.

## Version the spec

When the format changes, write a new dated spec block that says it supersedes
the previous one where they differ, rather than editing the old one. The
history explains why a post from three months ago looks different.

## Testing gotchas

- **Passing an em dash through `curl -d` mangles it** to a replacement
  character in this environment, which makes validation look broken when it is
  not. Write the JSON payload to a file and use `--data-binary @file`.
- Test the full cycle once, end to end: initialize, `tools/list`, `tools/call`,
  the auth failures, then a create that goes live on the site and is deleted
  again.
- Confirm the public URL the tool returns matches where the content actually
  renders. One site serves posts at root level while the MCP returned a
  `/blog/` path that only worked because of a redirect.

## Before calling it done

1. Wrong secret 401s, `GET` 405s, a notification 202s
2. `tools/list` works with no session
3. One real create reached the live site and was removed again
4. The tool descriptions match what the site renders today
5. The secret is in `.env.<name>`, not in any file that gets shared
6. The project's memory records the endpoint, the auth form, the tool list and
   where the secret lives
