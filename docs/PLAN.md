# Recruiter Pricing Platform: Project Plan & Team Split

## Context
This is a 36-hour hackathon. We are building an internal tool that **only recruiters** use. Clients and candidates do not use it. During an intake conversation, the recruiter fills in what the candidate wants. The tool then shows the **cost price** and the **advised hourly rate** for the client ("opdrachtgever") straight away. Sliders and switches let the recruiter try values such as wage, margin and sick days. Around this sit:
- candidate and vacancy lists
- a candidate-to-vacancy ranking
- an AI advisor that suggests tweaks when a candidate is over the client's budget

Stack: Django 6.1 (`rec_platform/` settings), DataTables 2.3.4, a PWA (installable web app), and uv for dependencies.

## Business rules
- **Salary → rate** (the candidate is known):
  `hourly = monthly × 3 ÷ 13 ÷ hours` → `cost = hourly × cost_factor` → `all_in = cost + travel_per_hour` → `rate = all_in + margin`
  - Example: €6000, 40h, factor 2.0 → €34.62 → €69.23 → +€2.13 = €71.36 → +€10 = **€81.36**.
  - With a client max of €120, the recruiter could propose e.g. €119.
- **Rate → salary** (before meeting a candidate):
  `cost = max_rate − margin` → `hourly = cost ÷ factor` → `monthly = hourly × hours × 13 ÷ 3`
  - Example: €120 → 110 → 55 → **€9,533.33** per month (an indicative maximum).
- **Inputs (for now):** employer (vacancy), desired gross salary, desired working hours, travel distance and travel means (car / public transport).
- **Cost price factor** (default 2.0, about 2× the gross labour cost) covers vacation days, sick leave and all other secondary employment conditions. They are not separate inputs.
- **Margin:** between €5 and €15 per hour, default €10.
- **Result:** cost price + travel costs + margin = advised tariff.
- **Travel distance** is calculated automatically from the candidate's home location to the vacancy location (OpenStreetMap geocoding + OSRM road distance, see `pricing/travel.py`). The recruiter can still overwrite it.
- **Travel costs:** `km_one_way × 2 × workdays × €/km ÷ hours_per_week`, where workdays = hours ÷ 8 (max 5). Rates: car €0.23/km, public transport €0.20/km (`pricing/constants.py`, *assumption: check with the client*).
- **Travel rule:** travel costs only count when the distance is known, and **not** when the client pays the travel costs itself (a setting per vacancy).
- **Warnings:**
  - The tariff is **more than 10% below** the client's max tariff. Candidates get rejected for being "too cheap".
  - The tariff is **above** the max tariff. This triggers the AI advisor.
- **Language:** the UI is available in Dutch and English.
- **Out of scope:** assessments, importing candidates, and access for clients or candidates.

## Data model
**Candidate** (`candidates.Candidate`):

| Group | Fields |
| --- | --- |
| Personal | `first_name`, `last_name`, `email`, `phone`, `city` (home location), `desired_role` |
| Status | `status` (intake / available / proposed / placed / inactive) |
| Salary & hours | `expected_salary_month`, `hours_per_week` (40) |
| Travel | `travel_distance_km` (one way, calculated automatically), `transport_type` (car / ov), `remote_days_per_week` (0–5, matching only) |
| Pricing | `cost_factor` (2.0), `margin_per_hour` (5–15, default 10), `proposed_rate` (nullable) |
| Links & meta | `vacancy` (FK to `clients.Vacancy`, nullable), `notes`, `created_at`, `updated_at` |

- The property `pricing` returns `pricing.engine.calculate(...)`.

**Client:** `name`, `industry`, `city`, `contact_name`, `contact_email`

**Vacancy:** `client` (FK), `title`, `address`, `city`, `max_rate_per_hour`, `client_pays_travel`, `hours_per_week`, `remote_days_allowed`, `min_salary`, `max_salary`, `skills`, `is_open`

## Architecture
```
manage.py
rec_platform/   settings.py, urls.py                          (Joseph)
core/           base layout, sidebar, toasts, modals, PWA, i18n (Joseph)
candidates/     candidate CRUD + DataTable + detail page        (Vidic)
pricing/        engine.py, calculator page, pricing API        (Teun)
clients/        clients, vacancies, matching.py, advisor.py    (Ivan)
docs/           this plan + per-person prompts
```

## Shared contracts
These must stay stable, because the other apps depend on them.

1. **Templates.** Every template does `{% extends "core/base.html" %}` and uses the blocks `title`, `heading`, `page_actions`, `content` and `extra_js`.
2. **Modals and toasts via `window.App`** (in `core/static/core/js/app.js`). Buttons carry `data-modal-url` and `data-table`.
   - **Opening:** the modal partial is loaded with a GET.
   - **Saving:** the form is sent with a POST that includes the CSRF header. The view returns JSON: either `{ok: true, message}`, or `{ok: false, html}` when the form has errors.
   - **On success:** the modal closes and a toast appears at the **top-left**. Then the table reloads with `table.ajax.reload(null, false)`.
   - **Deleting** works the same way: a confirmation modal opens, then a POST is sent, then the toast shows and the table reloads.
3. **DataTables.** Use 2.3.4 with Buttons 3.2.5, CardView 1.1.2 and jQuery 3.7.1. Tables load their data via ajax from a JSON endpoint. The last column holds the Edit and Delete buttons.
4. **Pricing.** `pricing.engine.calculate(PricingInput) -> PricingResult` is the single source of truth. Never copy the formulas. The JS calls the API instead.
5. **URL names:**
   - `core:dashboard`
   - `candidates:list|data|create|update|delete|detail`
   - `clients:vacancy_list|data|create|update|delete|detail|apply_tweak`
   - `pricing:calculator|calculate|reverse`
6. **Translations.** All UI strings go through `{% trans %}` / `gettext`. English is the source language and Dutch is the translation.

## Work split

| Who | Area | Owns | Prompt |
| --- | --- | --- | --- |
| **Joseph** | Platform shell, UX, PWA, i18n, dashboard, seed data | `core/`, `rec_platform/`, `README.md` | [prompts/joseph.md](prompts/joseph.md) |
| **Vidic** | Candidates: model, forms, DataTable CRUD with modals and toasts, detail page | `candidates/` | [prompts/vidic.md](prompts/vidic.md) |
| **Teun** | Pricing engine and interactive calculator (sliders and switches) | `pricing/` | [prompts/teun.md](prompts/teun.md) |
| **Ivan** | Clients and vacancies, matching or ranking, AI advisor | `clients/` | [prompts/ivan.md](prompts/ivan.md) |

Don't edit another person's app folder. Ask the owner instead.

## Git workflow
- **`main`** stays runnable. Merge into it through small PRs, each with one reviewer.
- **Branches:** `feat/joseph-shell`, `feat/vidic-candidates`, `feat/teun-pricing`, `feat/ivan-clients`.
- **Foundation first.** Before anyone branches, `main` needs the models, URL names, `base.html` and `app.js`.
- **Migrations.** Each app owns its own migrations. The only cross-app FK is `Candidate.vacancy` → `clients.Vacancy`.

## Verification
- Run `uv sync && uv run python manage.py migrate && uv run python manage.py seed_demo`.
- Run `uv run python manage.py test`. The pricing tests must reproduce **€81.36** and **€9,533.33**.
- Run `uv run python manage.py runserver`, then check in the browser:
  - Adding, editing and deleting a candidate works through the modals. Each action shows a top-left toast, and the table refreshes without a page reload.
  - The calculator sliders update the breakdown live.
  - For an over-budget candidate, the advisor suggests changes, and clicking "Apply" updates the candidate.
  - The NL/EN switch works.
  - The PWA can be installed.

## Hackathon tips
- **Daily sync.** Hold a 10-minute sync each day. The real coupling points are the engine API (Teun) and the candidate fields (Vidic), so agree on both on day 1.
- **Rebalancing.** Ivan's part is the heaviest. If Joseph finishes the shell early, Joseph takes over matching or the seed data.
- **Demo.** The calculator is the money shot. Rehearse the intake-conversation flow with it.
- **AI fallback.** Keep the rule-based fallback in the AI advisor, so the demo never breaks.
