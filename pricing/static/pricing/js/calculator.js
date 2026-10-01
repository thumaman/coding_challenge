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

    // Each group is a chain of operations, drawn as its own bordered block
    function renderBreakdown(container, groups) {
        container.innerHTML = groups.map((group) => `
            <table class="calc-group">
                <caption>${escapeHtml(group.title)}</caption>
                ${group.rows.map((r) => `
                    <tr class="${r.op === "=" ? "result" : ""}">
                        <td class="op">${escapeHtml(r.op)}</td>
                        <td class="label">${escapeHtml(r.label)}${r.detail ? `<small>${escapeHtml(r.detail)}</small>` : ""}</td>
                        <td class="value">${escapeHtml(formatValue(r))}</td>
                    </tr>`).join("")}
            </table>`).join("");
    }

    // ---- Salary -> tariff ----
    const forward = document.getElementById("forward-form");
    const vacancySelect = forward.querySelector("[name=vacancy_id]");
    const homeInput = forward.querySelector("[name=home_location]");
    const distanceInput = forward.querySelector("[name=travel_distance_km]");
    const distanceStatus = document.getElementById("distance-status");
    const paysTravel = forward.querySelector("[name=client_pays_travel]");

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
        document.getElementById("sum-travel").textContent = !result.travel_known ? T.unknown
            : result.client_pays_travel ? `${App.formatEuro(result.travel_per_hour)} (${T.paid_by_client})`
            : App.formatEuro(result.travel_in_tariff);
        document.getElementById("sum-margin").textContent = App.formatEuro(result.margin);
        document.getElementById("sum-tariff").textContent = App.formatEuro(result.advised_rate);

        const badge = document.getElementById("budget-badge");
        badge.className = `badge badge-${result.budget_status}`;
        badge.textContent = T.status[result.budget_status];
        document.getElementById("room").textContent =
            result.room_per_hour !== null ? fmt(T.room, {amount: App.formatEuro(result.room_per_hour)}) : "";
        renderBreakdown(document.getElementById("forward-breakdown"), result.breakdown);
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
            document.getElementById("reverse-salary").textContent = App.formatEuro(result.monthly_salary);
            renderBreakdown(document.getElementById("reverse-breakdown"), result.breakdown);
        } catch (err) { /* invalid input while typing */ }
    });
    reverse.addEventListener("input", runReverse);

    [forward, reverse].forEach((form) => form.addEventListener("submit", (e) => e.preventDefault()));
    updateForward();
    runReverse();

    // ---- Tabs ----
    document.querySelectorAll("[data-tab]").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-tab]").forEach((b) => b.classList.toggle("active", b === btn));
            document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== btn.dataset.tab; });
        });
    });
})();
