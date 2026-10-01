// Interactive calculator (owner: Teun). Inputs -> debounced POST to the pricing API -> render.
// No pricing formulas in JS: the engine in pricing/engine.py is the single source of truth.
(function () {
    "use strict";

    const debounce = (fn, ms = 150) => {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
    };

    function formData(form) {
        const data = {};
        form.querySelectorAll("input, select").forEach((el) => {
            if (!el.name) return;
            if (el.type === "checkbox") data[el.name] = el.checked;
            else if (el.value !== "") data[el.name] = el.value;
        });
        return data;
    }

    function renderBreakdown(table, rows) {
        table.innerHTML = rows.map((r) =>
            `<tr><td>${r.label}</td><td class="formula">${r.formula}</td><td class="value">${App.formatEuro(r.value)}</td></tr>`
        ).join("");
    }

    const BADGE_TEXT = {ok: "Within budget", too_low: "More than 10% under max: too cheap?", over: "Over budget", unknown: "No vacancy selected"};

    async function updateForward() {
        const form = document.getElementById("forward-form");
        const data = formData(form);
        form.querySelector(".travel-fields").hidden = !data.travel_known;
        const {result} = await App.post(form.dataset.endpoint, data);
        document.getElementById("advised-rate").textContent = App.formatEuro(result.final_rate);
        const badge = document.getElementById("budget-badge");
        badge.className = `badge badge-${result.budget_status}`;
        badge.textContent = BADGE_TEXT[result.budget_status];
        document.getElementById("room").textContent =
            result.room_per_hour !== null ? `Room: ${App.formatEuro(result.room_per_hour)} / hour` : "";
        renderBreakdown(document.getElementById("forward-breakdown"), result.breakdown);
    }

    async function updateReverse() {
        const form = document.getElementById("reverse-form");
        const {result} = await App.post(form.dataset.endpoint, formData(form));
        document.getElementById("reverse-salary").textContent = App.formatEuro(result.monthly_salary);
        renderBreakdown(document.getElementById("reverse-breakdown"), result.breakdown);
    }

    const handlers = {"forward-form": debounce(updateForward), "reverse-form": debounce(updateReverse)};

    document.querySelectorAll(".calc-form").forEach((form) => {
        form.addEventListener("input", (event) => {
            const output = event.target.closest(".field")?.querySelector(".slider-value");
            if (output) output.textContent = event.target.value;
            handlers[form.id]();
        });
        form.addEventListener("submit", (e) => e.preventDefault());
        handlers[form.id]();
    });

    document.querySelectorAll("[data-tab]").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-tab]").forEach((b) => b.classList.toggle("active", b === btn));
            document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== btn.dataset.tab; });
        });
    });
})();
