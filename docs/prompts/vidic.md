# Prompt for Vidic: candidates

```
You're working on a Django 6.1 hackathon project: an internal tool for recruiters that calculates the advised hourly rate for a candidate.

Apps and owners:
- core: Joseph (layout, plus the window.App modal/toast helpers)
- candidates: YOU, Vidic
- pricing: Teun (the calculation engine)
- clients: Ivan (clients, vacancies, AI advisor)

Run everything with `uv run python manage.py ...`. The full plan is in docs/PLAN.md.

YOU OWN: candidates/. Don't edit other apps' files.

Candidate model fields. Refine them, but don't rename them; the others depend on these names.
- Personal: first_name, last_name, email, phone, city, desired_role
- status: intake / available / proposed / placed / inactive
- Salary and hours: expected_salary_month (€ gross), hours_per_week (default 40)
- Travel and remote:
  - travel_known (bool). Travel cost only counts in the price when this is True.
  - travel_distance_km (one way)
  - transport_type: car / ov / bike / none
  - remote_days_per_week: 0–5
- Days off: vacation_days (default 25), sick_days_estimate (default 8)
- Benefits: secondary_benefits_month (€), benefits_description
- Pricing overrides: cost_factor (default 2.0), margin_per_hour (default 10.0), proposed_rate (nullable override)
- vacancy: FK to clients.Vacancy, nullable
- notes, created_at, updated_at
- Property `pricing`: returns pricing.engine.calculate(...) for this candidate. NEVER copy the formulas; import Teun's engine.

Tasks:
1. List page (candidates:list)
   - Use the DataTables setup from the provided template: 2.3.4 + Buttons + CardView, with layout topStart pageLength / topEnd search / bottomStart info / bottomEnd paging.
   - Load the data via ajax from candidates:data (JSON).
   - Columns: Name, Role, Status, Salary/month, Hours, Remote days, Vacancy, Advised rate, Actions.
   - Advised rate is a colour badge: green = within budget, orange = more than 10% under the vacancy max, red = over budget.
   - The last column holds Edit and Delete buttons, built with a render function.
   - Filters above the table: status, vacancy, "over budget only".
2. Add: a "+ Add candidate" button in {% block page_actions %} with data-modal-url pointing to candidates:create. It opens a floating window with the form.
3. Edit: opens the same form, prefilled (candidates:update). Saving returns JSON: {ok:true, message} on success, or {ok:false, html} with the form errors.
4. Delete: opens a confirmation modal (candidates:delete). After the POST, the table reloads and the candidate is gone.
5. Toasts: after every successful add, edit or delete, show a toast at the top-left via App.toast. Use window.App from core/static/core/js/app.js; don't write your own modal system.
6. ModelForm
   - Fieldsets: Personal / Salary & hours / Travel & remote / Days off & benefits / Pricing overrides.
   - The travel fields only show when travel_known is checked.
   - Validate ranges, e.g. remote days ≤ 5.
7. Detail page (candidates:detail)
   - A profile card.
   - {% include "pricing/_calculator_panel.html" %} (Teun's).
   - {% include "clients/_advisor_panel.html" %} (Ivan's), shown only when the candidate is over budget.
8. Tests for the CRUD views and the JSON responses. All strings go in {% trans %}.

Branch: feat/vidic-candidates.
```
