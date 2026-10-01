# Prompt for Joseph: platform shell, UX and PWA

```
You're working on a Django 6.1 hackathon project (36h, team of 4): an internal tool for recruiters (not clients, not candidates) that calculates the advised hourly rate to charge a client for a candidate, live during an intake conversation.

Apps and owners: core (YOU, Joseph), candidates (Vidic), pricing (Teun), clients (Ivan). Run with `uv run python manage.py ...` from the repo root; settings live in rec_platform/. Full plan: docs/PLAN.md.

YOU OWN: core/, rec_platform/, README.md. Don't edit other apps' files; ask the owner.

Shared contracts. The others depend on these, so keep them stable:
- Every page uses {% extends "core/base.html" %} with blocks: title, heading, page_actions, content, extra_js.
- static/core/js/app.js exposes window.App:
  - openModal(url): GETs a partial and injects it into #modal.
  - Submitting a form inside the modal POSTs via fetch with the CSRF header. The server returns JSON: {ok:true, message} on success, or {ok:false, html} with the re-rendered form and its errors.
  - On ok: close the modal, call App.toast(message, "success"), then reload the DataTable via table.ajax.reload(null, false).
  - confirmDelete(url): shows a confirmation modal, POSTs, shows a toast, reloads the table.
  - toast(msg, type): toasts appear at the TOP-LEFT.
  - Buttons use data-modal-url="..." and data-table="#tableId", so pages need no custom JS for CRUD.
- DataTables from CDN: 2.3.4, Buttons 3.2.5, CardView 1.1.2, plus jQuery 3.7.1.
- All UI strings go through {% trans %} / gettext. English is the source language; Dutch is the translation.

Tasks:
1. Settings:
   - Register the apps; configure TEMPLATES and STATIC.
   - LocaleMiddleware with LANGUAGES=[en, nl] and LOCALE_PATHS.
   - LoginRequiredMiddleware plus login and logout pages (recruiters only).
2. base.html:
   - Fixed left sidebar: Dashboard, Calculator, Candidates, Vacancies, Clients. Icons, active state, collapsible.
   - Topbar: page title, NL/EN switch (set_language), user menu.
   - Toast container (top-left) and the modal host.
3. app.css: an intuitive, practical, corporate theme.
   - Navy/slate palette, Inter font.
   - Styles for cards, tables, form groups, sliders, switches.
   - Status badges: green = within budget, orange = more than 10% under the max rate, red = over budget.
   - Responsive.
4. PWA:
   - manifest.webmanifest and icons.
   - sw.js: cache the app shell and CDN assets; network-first for HTML.
   - Register the service worker in base.html.
5. Dashboard (core:dashboard):
   - KPI cards: open vacancies, active candidates, candidates over budget, average margin.
   - A "recently added" list.
6. Management command seed_demo:
   - About 30 candidates, 5 clients and 12 vacancies with realistic Dutch data.
   - Some candidates must be over budget, so the AI advisor has something to show.
7. Dutch .po translations; a README with setup, the team split and the branch rules.

Branch: feat/joseph-shell. Merge into main through small PRs and keep main runnable. If you finish early, help Ivan with matching or seed data.
```
