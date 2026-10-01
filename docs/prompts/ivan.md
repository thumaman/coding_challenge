# Prompt for Ivan: clients, vacancies, matching and AI advisor

```
You're working on a Django 6.1 hackathon project: an internal recruiter tool that calculates the advised hourly rate to charge a client for a candidate.

Apps and owners:
- core: Joseph (layout, plus the window.App modal/toast helpers)
- candidates: Vidic
- pricing: Teun. pricing.engine.calculate is the single source of truth; never copy formulas.
- clients: YOU, Ivan

Full plan: docs/PLAN.md.

YOU OWN: clients/.

Models (already stubbed):
- Client: name, industry, city, contact_name, contact_email
- Vacancy: client FK, title, city, max_rate_per_hour, hours_per_week, remote_days_allowed, min_salary, max_salary, skills (text), is_open

Tasks:

1. Client and Vacancy CRUD, using the same pattern as Vidic's candidates:
   - DataTables 2.3.4, loaded via ajax from a JSON endpoint. The last column holds Edit/Delete.
   - "+ Add" opens a modal form (data-modal-url). Edit opens the same form prefilled.
   - Delete opens a confirmation modal, then reloads the table.
   - After each success, show a toast at the top-left via window.App.
   - Vacancy list filters: client, open/closed, max rate range.

2. matching.py: score(candidate, vacancy) returns 0–100 plus an explanation per criterion.
   - Budget fit: 40 points (advised rate vs max_rate_per_hour, via pricing.engine)
   - Salary in range: 20
   - Remote days compatible: 15
   - City/distance: 15
   - Role/skills keywords: 10

3. Vacancy detail page: the vacancy info, then the ranked candidates. Each shows a score bar, advised rate, budget badge and a link to the candidate.

4. advisor.py: suggest_tweaks(candidate, vacancy), for candidates whose rate exceeds the client's max.
   a. Deterministic solver first (always works). Using pricing.engine, compute the minimal single-lever change that brings rate ≤ max_rate:
      - lower salary (to €X)
      - lower margin (floor e.g. €5)
      - fewer vacation days (floor 20, the legal minimum)
      - more remote days (lowers travel cost)
      - fewer secondary benefits
      Also produce 1–2 combined options.
      Each option has: a changes dict, new_rate, savings_per_hour, and a short reason.
   b. Optional AI layer, only if ANTHROPIC_API_KEY is set:
      - Call Claude via the official `anthropic` Python SDK (model "claude-opus-5") with structured output.
      - Claude ranks the options and writes a 1–2 sentence, recruiter-friendly explanation for each.
      - It considers what the candidate cares about (the notes field).
      - On any error, or when the key is missing, fall back to rule-based ranking so the demo never breaks.

5. _advisor_panel.html (included on Vidic's candidate detail page): lists the options. Each option has an "Apply" button that:
   - POSTs to clients:apply_tweak and updates the candidate's fields
   - shows a toast at the top-left
   - refreshes the advisor panel and the calculator

6. Tests:
   - The solver brings an over-budget candidate within budget.
   - apply_tweak updates the fields.
   - The fallback works without an API key.

Branch: feat/ivan-clients. Coordinate with Teun on the engine API and with Vidic on the candidate fields.
```
