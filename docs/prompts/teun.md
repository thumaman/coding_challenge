# Prompt for Teun: pricing engine and interactive calculator

```
You're working on a Django 6.1 hackathon project: an internal tool for recruiters. During an intake conversation, the recruiter enters what the candidate wants and instantly sees the cost price and the advised hourly rate for the client. They then tweak the result with sliders and switches.

Apps and owners: core (Joseph), candidates (Vidic), pricing (YOU, Teun), clients (Ivan).
Your engine is the single source of truth. Vidic's candidates, plus Ivan's matching and AI advisor, all import it. Full plan: docs/PLAN.md.

YOU OWN: pricing/.

Business rules (from the client; tests must match to the cent):

A) Salary → rate (candidate known)
   hourly      = monthly × 3 ÷ 13 ÷ hours_per_week
   cost        = hourly × cost_factor          (default 2.0)
   all_in_cost = cost + travel_per_hour
   rate        = all_in_cost + margin          (default €10/h)
   Example: €6000, 40h, factor 2.0
     → €34.62/h → €69.23 → +€2.13 travel = €71.36 → +€10 = €81.36.
   If the client's max is €120, the recruiter may propose e.g. €119.

B) Rate → salary (before meeting a candidate; travel EXCLUDED)
   cost    = max_rate − margin
   hourly  = cost ÷ factor
   monthly = hourly × hours × 13 ÷ 3
   Example: €120 − 10 = 110 → ÷2 = €55 → ×40 = €2200/week → €9,533.33/month (indicative max).

C) Business rule: travel cost is only part of the calculation when a concrete candidate's travel data is known (travel_known=True).

D) Extensions. Put the parameters in pricing/constants.py and mark them as assumptions to validate with the client.
   - Travel:
       travel_per_hour = km_one_way × 2 × office_days × €/km ÷ hours_per_week
       office_days     = days_worked − remote_days
       €/km: car 0.23, ov 0.20, bike/none 0
   - Days off:
       effective_factor = base_factor × base_productive_days ÷ productive_days
       productive_days  = 261 − public_holidays − vacation_days − sick_days
       reference values: 25 vacation days, 8 sick days
   - Secondary benefits (€/month) are added to the hourly cost as monthly × 3 ÷ 13 ÷ hours.

E) Warnings
   - Proposed rate > client max: "over budget".
   - Proposed rate more than 10% below client max: candidates get rejected for being too cheap.

Tasks:
1. engine.py
   - Pure Python with Decimal; round only on output.
   - Dataclasses: PricingInput / PricingResult.
   - Functions: calculate(input), rate_to_salary(...), travel_cost_per_hour(...), effective_factor(...).
   - PricingResult includes a step-by-step `breakdown` list (label, formula, value) for transparency, and budget_status: "ok" / "too_low" / "over" / "unknown".
2. JSON endpoints: POST /api/pricing/calculate/ and /api/pricing/reverse/ (URL names pricing:calculate and pricing:reverse).
3. Calculator page (pricing:calculator, extends core/base.html), with two tabs:
   a. "Salary → rate"
      - Sliders: salary, hours, cost factor, margin, remote days, vacation days, sick days.
      - Switches: travel known, car/ov.
      - Optional vacancy selector to set the max rate.
      - Output: live breakdown, a big advised-rate figure, an editable proposed-rate field, and a visual bar showing proposed vs max rate with the −10% band.
   b. "Rate → salary"
      - Inputs: max rate, margin, factor, hours.
      - Output: indicative max monthly salary, with an "excl. travel costs" disclaimer.
4. calculator.js: inputs → debounced (~150 ms) fetch → update the DOM. No formulas in JS.
5. _calculator_panel.html: a reusable partial for Vidic's candidate detail page.
   - Prefilled from a candidate.
   - A "Save to candidate" button: POST, then App.toast at the top-left.
6. tests.py
   - Both examples, exactly.
   - The remote-days effect.
   - Travel is ignored when travel_known=False.
   - The warning thresholds.

Branch: feat/teun-pricing. Agree the PricingInput fields with Vidic and Ivan on day 1; don't change them silently afterwards.
```
