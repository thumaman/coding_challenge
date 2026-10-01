# Remaining work

The foundation is on `main`. This list is what's still open from [PLAN.md](PLAN.md).

In the code, search for `TODO(<your name>)` to find where to continue. Tick items off in your PR.

## Joseph: layout, installable app, translations
- [x] **Dutch translations.** Done. After adding new strings: `makemessages -l nl --ignore=.venv`, translate them in `core/locale/nl/LC_MESSAGES/django.po`, then run `compilemessages --ignore=.venv` and commit the `.mo` too.
- [ ] **App icons.** Add PNG icons (192 and 512 px) to the manifest and an "install app" button. Some browsers won't install the app with only an SVG icon.
- [ ] **Dashboard.** Make the KPI cards clickable and add charts.
- [ ] *(Idea from the notes)* Notify the recruiter when a candidate matches a vacancy above X%.

## Vidic: candidates
- [ ] A nicer layout for the candidate detail page.
- [ ] More form checks, e.g. remote days can't exceed the number of days worked.
- [ ] More tests: filters, validation, the over-budget badge.

## Teun: pricing
- [ ] **Calculator page.** Add a bar showing the proposed rate against the client's max, with the −10% band.
- [x] **Prefill from a candidate.** Done: `/calculator/?candidate=<id>`.
- [ ] **Interactive pricing panel.** Make `_calculator_panel.html` on the candidate page interactive: sliders, plus a "Save to candidate" button that saves the values and shows a toast.
- [ ] **Check the travel cost assumptions with the client.**
  - Rates: car €0.25/km tax-free (214 working days/year), public transport €10/km capped at €400 (NS Flex Altijd Vrij).
  - Should public transport use real fares (e.g. an NS API) instead of a rate per km?

## Ivan: clients, vacancies, matching, AI advisor
- [ ] **Clients page.** Build a table with add/edit/delete pop-ups. It only shows cards now; copy `vacancy_list.html`.
- [ ] **Vacancy list filters.** Client, open/closed, and max rate range.
- [ ] **Matching.** Use real distance instead of comparing city names, and improve keyword matching.
- [ ] **Vacancy page.**
  - Show the score breakdown per candidate.
  - Add a button that links a candidate to the vacancy.
- [ ] **Tests.**
  - Combined advisor options.
  - Claude ranking, tested with a fake (mocked) API client.

## Ivan, after the pricing changes
- [ ] The advisor's options are now: lower salary, lower margin (min €5), client pays travel costs, cheaper travel means, and a combined option. Tune the ranking.

## Everyone
- [ ] **Browser test.** Click through the whole app: add, edit and delete candidates, check the toasts, move the calculator sliders, use the advisor's "Apply" button.
- [ ] **Claude test.** Run the AI advisor once with `ANTHROPIC_API_KEY` set. So far only the rule-based fallback has been tested.
- [ ] **Demo rehearsal.** Practise the intake-conversation flow with the calculator.
