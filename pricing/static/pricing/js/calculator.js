// Interactive calculator (owner: Teun). Inputs -> debounced POST to the pricing API -> render.
// No pricing formulas in JS: the engine in pricing/engine.py is the single source of truth.
// Also drives the candidate form page: inputs are found via data-role, and data-field-map on the form
// renames its (model) field names to the pricing API names. There, the vacancies are rows (one per vacancy,
// see candidates/_link_row.html) with their own travel distance and toggle; the result card shows the active row.
(function () {
    "use strict";

    const T = JSON.parse(document.getElementById("calc-i18n").textContent);
    const fmt = (template, values) => template.replace(/%\((\w+)\)s/g, (_, key) => values[key]);
    const debounce = (fn, ms = 150) => {
        let timer;
        return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
    };

    function formData(form) {
        const data = {};
        form.querySelectorAll("input[name], select[name]").forEach((el) => {
            if (el.type === "checkbox") data[el.name] = el.checked;
            else if (el.type === "radio") { if (el.checked) data[el.name] = el.value; }
            else if (el.value !== "") data[el.name] = el.value;
        });
        return data;
    }

    function formatValue(row) {
        switch (row.kind) {
            case "eur": return App.formatEuro(row.value);
            case "hours": return `${row.value} h`;
            default: return row.value;
        }
    }

    const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

    // Calculation steps in a result tile's dropdown (twin of pricing/_steps.html)
    function renderSteps(container, steps) {
        container.innerHTML = steps.map((r) => `
            <div class="${r.op === "=" ? UI.step_result_row : UI.step_row}">
                <span class="${UI.step_op}">${escapeHtml(r.op)}</span>
                <span>${escapeHtml(r.label)}${r.detail ? `<span class="${UI.step_detail}">${escapeHtml(r.detail)}</span>` : ""}</span>
                <span class="${UI.step_value}">${escapeHtml(formatValue(r))}</span>
            </div>`).join("");
    }

    // ---- Searchable vacancy picker over the hidden <select> ----
    // Single mode (calculator): the <select> stays the source of truth: picking an option sets its value and fires
    // "change". Multiple mode (candidate form): picking calls onPick(option), isPicked(value) marks options already
    // picked. Either way the list closes after a pick.
    function vacancyPicker(select, {multiple = false, isPicked = null, onPick = null} = {}) {
        const combo = document.getElementById("vacancy-combo");
        const valueBox = document.getElementById("vacancy-combo-value");
        const search = document.getElementById("vacancy-combo-search");
        const list = document.getElementById("vacancy-combo-list");
        const options = [...select.options];
        let active = -1;

        const pill = (o) => `<span class="${UI.combo_pill}">${escapeHtml(T.max)} ${escapeHtml(App.formatEuro(o.dataset.max))}</span>`;

        function renderValue() {
            const o = select.selectedOptions[0];
            valueBox.innerHTML = !multiple && o && o.value
                ? `<span class="flex min-w-0 flex-col">
                       <span class="truncate font-medium">${escapeHtml(o.dataset.title)}</span>
                       <span class="truncate text-xs text-gray-500">${escapeHtml(o.dataset.client)} · ${escapeHtml(o.dataset.location)}</span>
                   </span>${pill(o)}`
                : `<span class="text-gray-400">${escapeHtml(multiple ? T.vacancy_add : T.vacancy_placeholder)}</span>`;
        }

        const rows = () => [...list.querySelectorAll("[role=option]")];
        function setActive(index) {
            const all = rows();
            active = Math.max(0, Math.min(index, all.length - 1));
            all.forEach((row, i) => row.toggleAttribute("data-active", i === active));
            if (all[active]) all[active].scrollIntoView({block: "nearest"});
        }

        function renderList() {
            const q = search.value.trim().toLowerCase();
            const matches = options.filter((o) => o.value
                && `${o.dataset.title} ${o.dataset.client} ${o.dataset.location}`.toLowerCase().includes(q));
            const isSelected = (o) => multiple ? isPicked(o.value) : o.selected;
            const row = (o, inner) => `<button type="button" role="option" class="${UI.combo_option}" data-value="${escapeHtml(o.value)}"
                aria-selected="${isSelected(o)}">${inner}</button>`;
            let html = q || multiple ? "" : row(options[0], `<span class="text-gray-500">${escapeHtml(T.no_vacancy)}</span>`);
            let client = null;
            matches.forEach((o) => {
                if (o.dataset.client !== client) {
                    client = o.dataset.client;
                    html += `<div class="${UI.combo_group}" role="presentation">${escapeHtml(client)}</div>`;
                }
                const check = multiple && isSelected(o) ? `<span class="shrink-0 text-blue-600" aria-hidden="true">&#10003;</span>` : "";
                html += row(o, `${check}<span class="flex min-w-0 flex-col">
                        <span class="truncate">${escapeHtml(o.dataset.title)}</span>
                        <span class="truncate text-xs text-gray-500">${escapeHtml(o.dataset.location)}</span>
                    </span>${pill(o)}`);
            });
            list.innerHTML = html || `<div class="${UI.combo_empty}">${escapeHtml(T.no_results)}</div>`;
            const selected = rows().findIndex((r) => r.getAttribute("aria-selected") === "true");
            setActive(q || selected < 0 ? 0 : selected);
        }

        function pick(value) {
            if (multiple) {
                if (!isPicked(value)) onPick(select.querySelector(`option[value="${CSS.escape(value)}"]`));
            } else {
                select.value = value;
                select.dispatchEvent(new Event("change", {bubbles: true}));
            }
            combo.open = false;
            renderValue();
            combo.querySelector("summary").focus();
        }

        combo.addEventListener("toggle", () => {
            if (!combo.open) return;
            search.value = "";
            renderList();
            search.focus();
        });
        search.addEventListener("input", (event) => {
            event.stopPropagation(); // typing in the search box is not a calculator input
            renderList();
        });
        search.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                setActive(active + (event.key === "ArrowDown" ? 1 : -1));
            } else if (event.key === "Enter") {
                event.preventDefault();
                const row = rows()[active];
                if (row) pick(row.dataset.value);
            }
        });
        list.addEventListener("mousemove", (event) => {
            const row = event.target.closest("[role=option]");
            if (row) setActive(rows().indexOf(row));
        });
        list.addEventListener("click", (event) => {
            const row = event.target.closest("[role=option]");
            if (row) pick(row.dataset.value);
        });

        renderValue();
    }

    // ---- Salary -> tariff ----
    const forward = document.getElementById("forward-form");
    const fieldMap = JSON.parse(forward.dataset.fieldMap || "{}");
    const homeInput = forward.querySelector("[data-role=home]");
    const linkRows = document.getElementById("link-rows"); // candidate form only

    function renderResult(result) {
        document.getElementById("sum-cost").textContent = App.formatEuro(result.cost_price);
        // Travel is only shown as part of the tariff when it is known and not paid by the client
        document.getElementById("sum-travel-part").hidden = !result.travel_known || result.client_pays_travel;
        document.getElementById("sum-travel").textContent = App.formatEuro(result.travel_in_tariff);
        document.getElementById("sum-margin").textContent = App.formatEuro(result.margin);
        document.getElementById("sum-tariff").textContent = App.formatEuro(result.advised_rate);

        const badge = document.getElementById("budget-badge");
        badge.className = App.badgeClass(result.budget_status);
        badge.textContent = T.status[result.budget_status];
        document.getElementById("room").textContent =
            result.room_per_hour !== null ? fmt(T.room, {amount: App.formatEuro(result.room_per_hour)}) : "";
        renderSteps(document.getElementById("cost-steps"), result.cost_steps);
        renderSteps(document.getElementById("travel-steps"), result.travel_steps);
    }

    function baseData() {
        const data = {};
        Object.entries(formData(forward)).forEach(([name, value]) => {
            if (!name.startsWith(`${linkRows && linkRows.dataset.prefix}-`)) data[fieldMap[name] || name] = value;
        });
        delete data.home_location;
        return data;
    }

    // One-way distance home -> work location into `input`, with a status text. Calls done() afterwards.
    async function fetchDistance(destination, input, status, done) {
        const origin = homeInput.value.trim();
        if (!destination || !origin) {
            status.textContent = T.distance_needed;
            return;
        }
        status.textContent = T.distance_loading;
        const params = new URLSearchParams({origin, destination});
        try {
            const response = await fetch(`${forward.dataset.distanceEndpoint}?${params}`);
            const data = await response.json();
            if (!data.ok) throw new Error(data.message);
            input.value = data.km;
            status.textContent = data.source === "route"
                ? fmt(T.distance_route, {from: origin, to: destination}) : T.distance_estimate;
        } catch (err) {
            input.value = "";
            status.textContent = T.distance_failed;
        }
        input.dispatchEvent(new Event("change", {bubbles: true})); // autosave + recalculation
        done();
    }

    // The candidate form submits for real; the calculator forms never do
    if (forward.method !== "post") forward.addEventListener("submit", (e) => e.preventDefault());

    if (linkRows) candidateRows(); else calculatorForward();

    // Calculator: one vacancy (picker over a <select>), travel fields of its own
    function calculatorForward() {
        const vacancySelect = forward.querySelector("[data-role=vacancy]");
        const distanceInput = forward.querySelector("[data-role=distance]");
        const distanceStatus = document.getElementById("distance-status");
        const paysTravel = forward.querySelector("[name=client_pays_travel]");
        const travelFields = document.getElementById("travel-fields");
        vacancyPicker(vacancySelect);

        // Home location, travel means and distance don't apply when the client pays the travel costs
        const syncTravelFields = () => { travelFields.disabled = paysTravel.checked; };
        paysTravel.addEventListener("change", syncTravelFields);

        const runForward = debounce(async () => {
            try {
                renderResult((await App.post(forward.dataset.endpoint, baseData())).result);
            } catch (err) { /* e.g. an empty or invalid number while typing */ }
        });
        const runDistance = debounce(() => {
            const option = vacancySelect.selectedOptions[0];
            fetchDistance(option && option.dataset.location, distanceInput, distanceStatus, runForward);
        }, 600);

        vacancySelect.addEventListener("change", () => {
            const option = vacancySelect.selectedOptions[0];
            // Picking a vacancy applies its default for who pays the travel costs
            paysTravel.checked = Boolean(option && option.dataset.paysTravel === "1");
            syncTravelFields();
            runDistance();
        });
        homeInput.addEventListener("input", runDistance);
        forward.addEventListener("input", (event) => { if (event.target !== homeInput) runForward(); });
        forward.addEventListener("change", runForward);
        runForward();
    }

    // Candidate form: one row per vacancy (a formset form). Each row gets its own tariff badge;
    // the result card shows the active row (the first one, or the one last clicked).
    function candidateRows() {
        const prefix = linkRows.dataset.prefix;
        const totalForms = forward.querySelector(`[name=${prefix}-TOTAL_FORMS]`);
        const template = document.getElementById("link-row-template");
        const empty = document.getElementById("link-empty");
        const vacancySelect = document.getElementById("id_vacancy");
        const field = (row, name) => row.querySelector(`[data-field=${name}]`);
        const rows = () => [...linkRows.querySelectorAll("[data-link-row]:not([hidden])")];
        let active = null;

        const isPicked = (value) => rows().some((row) => field(row, "vacancy").value === value);

        function activate(row) {
            active = row;
            linkRows.querySelectorAll("[data-link-row]").forEach((r) => r.toggleAttribute("data-active", r === row));
        }

        function syncTravel(row) {
            row.querySelector("[data-distance-box]").toggleAttribute("data-dimmed", field(row, "pays").checked);
        }

        function rowDistance(row) {
            fetchDistance(row.dataset.location, field(row, "distance"), row.querySelector("[data-slot=distance-status]"), runRows);
        }

        function addRow(option) {
            const index = Number(totalForms.value);
            const holder = document.createElement("div");
            holder.innerHTML = template.innerHTML.replace(/__prefix__/g, index);
            const row = holder.firstElementChild;
            row.dataset.location = option.dataset.location;
            row.dataset.max = option.dataset.max;
            field(row, "vacancy").value = option.value;
            field(row, "pays").checked = option.dataset.paysTravel === "1"; // the vacancy's default
            row.querySelector("[data-slot=title]").textContent = option.dataset.title;
            row.querySelector("[data-slot=subtitle]").textContent = `${option.dataset.client} · ${option.dataset.location}`;
            row.querySelector("[data-slot=max]").textContent = `${T.max} ${App.formatEuro(option.dataset.max)}`;
            linkRows.appendChild(row);
            totalForms.value = index + 1;
            setupRow(row);
            if (!active) activate(row);
            empty.hidden = true;
            field(row, "vacancy").dispatchEvent(new Event("change", {bubbles: true})); // tariffs + autosave
            rowDistance(row);
        }

        function removeRow(row) {
            // Always kept as a deleted form: the formset then never sees a half-empty one
            field(row, "delete").checked = true;
            row.hidden = true;
            row.removeAttribute("data-active");
            if (active === row) activate(rows()[0] || null);
            empty.hidden = rows().length > 0;
            field(row, "delete").dispatchEvent(new Event("change", {bubbles: true}));
        }

        function setupRow(row) {
            syncTravel(row);
            row.addEventListener("focusin", () => { if (active !== row) { activate(row); runRows(); } });
            row.addEventListener("click", (event) => {
                if (event.target.closest("[data-remove]")) removeRow(row);
                else if (active !== row) { activate(row); runRows(); }
            });
            field(row, "pays").addEventListener("change", () => syncTravel(row));
        }

        function rowData(row) {
            const data = {
                ...baseData(),
                vacancy_id: field(row, "vacancy").value,
                client_pays_travel: field(row, "pays").checked,
            };
            if (field(row, "distance").value !== "") data.travel_distance_km = field(row, "distance").value;
            if (field(row, "proposed").value !== "") data.proposed_rate = field(row, "proposed").value;
            return data;
        }

        async function updateRows() {
            const all = rows();
            if (!all.length) { // no vacancy yet: the tariff without a budget to compare with
                try { renderResult((await App.post(forward.dataset.endpoint, baseData())).result); } catch (err) { /* typing */ }
                return;
            }
            await Promise.all(all.map(async (row) => {
                let result;
                try {
                    ({result} = await App.post(forward.dataset.endpoint, rowData(row)));
                } catch (err) {
                    return; // e.g. an empty or invalid number while typing
                }
                const badge = row.querySelector("[data-slot=tariff]");
                badge.className = App.badgeClass(result.budget_status);
                badge.textContent = App.formatEuro(result.final_rate);
                if (row === active) renderResult(result);
            }));
        }

        const runRows = debounce(updateRows);
        const runDistances = debounce(() => rows().forEach(rowDistance), 600);

        vacancyPicker(vacancySelect, {multiple: true, isPicked, onPick: addRow});
        linkRows.querySelectorAll("[data-link-row]").forEach(setupRow);
        activate(rows()[0] || null);

        homeInput.addEventListener("input", runDistances);
        forward.addEventListener("input", (event) => { if (event.target !== homeInput) runRows(); });
        forward.addEventListener("change", runRows);
        updateRows();
    }

    // ---- Tariff -> salary (calculator page only) ----
    const reverse = document.getElementById("reverse-form");
    if (!reverse) return;
    const runReverse = debounce(async () => {
        try {
            const {result} = await App.post(reverse.dataset.endpoint, formData(reverse));
            document.getElementById("reverse-cost").textContent = App.formatEuro(result.cost_price);
            document.getElementById("reverse-hourly").textContent = App.formatEuro(result.hourly_wage);
            document.getElementById("reverse-salary").textContent = App.formatEuro(result.monthly_salary);
            renderSteps(document.getElementById("reverse-steps"), result.steps);
        } catch (err) { /* invalid input while typing */ }
    });
    reverse.addEventListener("input", runReverse);

    reverse.addEventListener("submit", (e) => e.preventDefault());
    runReverse();

    // ---- Tabs ----
    document.querySelectorAll("[data-tab]").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", b === btn));
            document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== btn.dataset.tab; });
        });
    });
})();
