# TalentRate: recruiter pricing platform

TalentRate is an internal tool for recruiters. It calculates the advised hourly rate to charge a client for a candidate, live during an intake conversation.

The full plan, business rules and team split are in [docs/PLAN.md](docs/PLAN.md). Each person's task prompt is in [docs/prompts/](docs/prompts/).

## Quick start

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo        # demo data + login recruiter / recruiter
uv run python manage.py runserver
```

Open http://127.0.0.1:8000 and log in with `recruiter` / `recruiter`.

Optional: set `ANTHROPIC_API_KEY` to let Claude rank and explain the AI advisor's suggestions. Without the key, the advisor still works using rule-based ranking.

```bash
uv run python manage.py test             # pricing tests must reproduce €81.36 and €9,533.33
```

## Who owns what

| Who | App | Branch |
| --- | --- | --- |
| Joseph | `core/`, `rec_platform/`: layout, sidebar, toasts/modals, PWA, i18n, dashboard, seed data | `feat/joseph-shell` |
| Vidic | `candidates/`: candidate model, DataTable CRUD, detail page | `feat/vidic-candidates` |
| Teun | `pricing/`: `engine.py` (single source of truth), calculator page, pricing API | `feat/teun-pricing` |
| Ivan | `clients/`: clients, vacancies, `matching.py`, `advisor.py` (AI advisor) | `feat/ivan-clients` |

Look for `TODO(<name>)` in the code. Those markers show where each person continues.

## Shared contracts (don't break these without telling the team)

- **Pages** use `{% extends "core/base.html" %}` and fill these blocks: `title`, `heading`, `page_actions`, `content`, `extra_js`.
- **Modals** (`core/static/core/js/app.js` + `core/modals.py`):
  - Give a button `data-modal-url="<url>"` and `data-table="#tableId"`, or `data-reload` instead of `data-table`.
  - The view uses `ModalFormMixin` / `ModalDeleteMixin`. It returns `{ok, message}` or `{ok: false, html}`.
  - On success, the modal closes, a toast appears top-left, and the DataTable reloads. No page-specific JS is needed.
- **Other forms** can use `data-ajax` (with `data-reload` or `data-table`) to get the same POST → toast behaviour.
- **Pricing:** always call `pricing.engine.calculate(PricingInput(...))`, or `candidate.pricing` / `candidate.pricing_for(vacancy)`. Never copy the formulas. JavaScript calls `/api/pricing/calculate/` instead.
- **Translations:** UI strings go in `{% trans %}` / `gettext`.

## Git workflow

1. `git checkout main && git pull`.
2. `git checkout -b feat/<name>-<topic>`.
3. Make small commits, then open a PR into `main` with one reviewer. Keep `main` runnable.
4. Changed a model? Run `uv run python manage.py makemigrations <your_app>` and commit the migration.
