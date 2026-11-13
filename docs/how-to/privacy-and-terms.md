---
title: Privacy and terms pages
group: How-to guides
order: 40
summary: Edit the platform's privacy and terms text, and let a space replace it with its own.
---

# Privacy and terms pages

Every installation serves a **privacy** page and a **terms** page. They start as shipped text that describes what Space Works actually does (accounts, requests, loans, evidence photos, events, email), translated into the languages the app supports. Nothing needs doing for a fresh install.

## Who edits what

- **Platform superadmin** — replaces the default for the whole installation, per language, under the platform legal pages (`PUT /api/v1/admin/platform/legal-pages/{privacy|terms}`, body `markdown` and optional `language`). `DELETE` returns a page to the shipped default.
- **A Space Manager** — may write the space's own page (`PUT /api/v1/admin/makerspace/{id}/legal-pages/{privacy|terms}`); a blank text removes it. Visitors of that space then see the space's text. Turn this off with the `legal.space_pages` switch; saved text is kept.

Pages are Markdown. They are shown as text, never as raw HTML.

## Where visitors read them

`GET /api/v1/discover/legal/{privacy|terms}/` needs no sign-in. Add `?space=<slug>` to get that space's own text when it wrote one. The order is: the space's text, the platform's text for the reader's language, the platform's language-neutral text, the shipped default. The response says which one it is (`source`: `space`, `platform` or `default`).

## Check it worked

Open the public page, then change the text and reload. Every change is in the audit log (`platform.legal_page_updated`, `makerspace.legal_page_updated`), recording the page, the language and the length, never the text.
