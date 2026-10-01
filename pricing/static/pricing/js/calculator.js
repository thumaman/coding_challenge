// Interactive calculator (owner: Teun). Inputs -> debounced POST to the pricing API -> render.
// No pricing formulas in JS: the engine in pricing/engine.py is the single source of truth.
(function () {
    "use strict";

    const T = JSON.parse(document.getElementById("calc-i18n").textContent);
    const fmt = (template, values) => template.replace(/%\((\w+)\)s/g, (_, key) => values[key]);
    const debounce = (fn, ms = 150) => {
        let timer;
        return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
    };

    // ---- Slider <-> number box sync (the number box is the named input) ----
    document.querySelectorAll("input[type=range][data-sync]").forEach((range) => {
        const number = document.getElementById(range.dataset.sync);
        range.addEventListener("input", () => {
            number.value = range.value;
            number.dispatchEvent(new Event("input", {bubbles: true}));
        });
        number.addEventListener("input", () => { range.value = number.value; });
    });

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
    // The <select> stays the source of truth: picking an option sets its value and fires "change".
    function vacancyPicker(select) {
        const combo = document.getElementById("vacancy-combo");
        const valueBox = document.getElementById("vacancy-combo-value");
        const search = document.getElementById("vacancy-combo-search");
        const list = document.getElementById("vacancy-combo-list");
        const options = [...select.options];
        let active = -1;

        const pill = (o) => `<span class="${UI.combo_pill}">${escapeHtml(T.max)} ${escapeHtml(App.formatEuro(o.dataset.max))}</span>`;

        function renderValue() {
            const o = select.selectedOptions[0];
            valueBox.innerHTML = o && o.value
                ? `<span class="flex min-w-0 flex-col">
                       <span class="truncate font-medium">${escapeHtml(o.dataset.title)}</span>
                       <span class="truncate text-xs text-gray-500">${escapeHtml(o.dataset.client)} · ${escapeHtml(o.dataset.location)}</span>
                   </span>${pill(o)}`
                : `<span class="text-gray-400">${escapeHtml(T.vacancy_placeholder)}</span>`;
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
            const row = (o, inner) => `<button type="button" role="option" class="${UI.combo_option}" data-value="${escapeHtml(o.value)}"
                aria-selected="${o.selected}">${inner}</button>`;
            let html = q ? "" : row(options[0], `<span class="text-gray-500">${escapeHtml(T.no_vacancy)}</span>`);
            let client = null;
            matches.forEach((o) => {
                if (o.dataset.client !== client) {
                    client = o.dataset.client;
                    html += `<div class="${UI.combo_group}" role="presentation">${escapeHtml(client)}</div>`;
                }
                html += row(o, `<span class="flex min-w-0 flex-col">
                        <span class="truncate">${escapeHtml(o.dataset.title)}</span>
                        <span class="truncate text-xs text-gray-500">${escapeHtml(o.dataset.location)}</span>
                    </span>${pill(o)}`);
            });
            list.innerHTML = html || `<div class="${UI.combo_empty}">${escapeHtml(T.no_results)}</div>`;
            const selected = rows().findIndex((r) => r.getAttribute("aria-selected") === "true");
            setActive(q || selected < 0 ? 0 : selected);
        }

        function pick(value) {
            select.value = value;
            select.dispatchEvent(new Event("change", {bubbles: true}));
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
    const vacancySelect = forward.querySelector("[name=vacancy_id]");
    const homeInput = forward.querySelector("[name=home_location]");
    const distanceInput = forward.querySelector("[name=travel_distance_km]");
    const distanceStatus = document.getElementById("distance-status");
    const paysTravel = forward.querySelector("[name=client_pays_travel]");
    const travelFields = document.getElementById("travel-fields");
    vacancyPicker(vacancySelect);

    // Home location, travel means and distance don't apply when the client pays the travel costs
    const syncTravelFields = () => { travelFields.disabled = paysTravel.checked; };
    paysTravel.addEventListener("change", syncTravelFields);

    async function updateForward() {
        const data = formData(forward);
        delete data.home_location;
        let result;
        try {
            ({result} = await App.post(forward.dataset.endpoint, data));
        } catch (err) {
            return; // e.g. an empty or invalid number while typing
        }
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

    async function updateDistance() {
        const option = vacancySelect.selectedOptions[0];
        const destination = option && option.dataset.location;
        const origin = homeInput.value.trim();
        if (!destination || !origin) {
            distanceStatus.textContent = T.distance_needed;
            return;
        }
        distanceStatus.textContent = T.distance_loading;
        const params = new URLSearchParams({origin, destination});
        try {
            const response = await fetch(`${forward.dataset.distanceEndpoint}?${params}`);
            const data = await response.json();
            if (!data.ok) throw new Error(data.message);
            distanceInput.value = data.km;
            distanceStatus.textContent = data.source === "route"
                ? fmt(T.distance_route, {from: origin, to: destination}) : T.distance_estimate;
        } catch (err) {
            distanceInput.value = "";
            distanceStatus.textContent = T.distance_failed;
        }
        runForward();
    }

    const runForward = debounce(updateForward);
    const runDistance = debounce(updateDistance, 600);

    vacancySelect.addEventListener("change", () => {
        const option = vacancySelect.selectedOptions[0];
        paysTravel.checked = option && option.dataset.paysTravel === "1";
        syncTravelFields();
        runDistance();
    });
    homeInput.addEventListener("input", runDistance);
    forward.addEventListener("input", (event) => {
        if (event.target !== homeInput) runForward();
    });
    forward.addEventListener("change", runForward);

    // ---- Tariff -> salary ----
    const reverse = document.getElementById("reverse-form");
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

    [forward, reverse].forEach((form) => form.addEventListener("submit", (e) => e.preventDefault()));
    updateForward();
    runReverse();

    // ---- Tabs ----
    document.querySelectorAll("[data-tab]").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", b === btn));
            document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== btn.dataset.tab; });
        });
    });
})();
