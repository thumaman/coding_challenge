/*
 * Shared front-end helpers (owner: Joseph). See docs/PLAN.md, "Shared contracts".
 *
 * Declarative usage, no page JS needed:
 *   <button data-modal-url="/candidates/new/" data-table="#candidates">+ Add</button>
 *
 * The modal partial must contain a <form class="modal-form">. On submit it is POSTed with fetch.
 * The server answers {ok: true, message} or {ok: false, html}. On success the modal closes, a toast
 * is shown top-left, and the DataTable named in data-table is reloaded (or the page, with data-reload).
 *
 * Styling is Tailwind only. Shared component classes come from core/ui.py as window.UI.
 */

function paintSlider(el) {
  const min = parseFloat(el.min) || 0;
  const max = parseFloat(el.max) || 100;
  const v = Math.min(1, Math.max(0, (el.value - min) / (max - min)));
  el.style.setProperty('--v', v);
}

(function () {
    "use strict";

    const I18N = Object.assign({
        actions: "Actions",
        load_failed: "Could not load the form.",
        error: "Something went wrong. Please try again.",
    }, window.APP_I18N || {});
    const UI = JSON.parse(document.getElementById("ui-classes").textContent);
    const modal = document.getElementById("modal");
    const modalBody = document.getElementById("modal-body");
    let context = {}; // {table, reload} of the button that opened the current modal

    function csrfToken() {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        if (match) return match[1];
        const input = document.querySelector("input[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    function toast(message, type = "success", timeout = 3500) {
        if (!message) return;
        const el = document.createElement("div");
        el.className = `${UI.toast} ${UI.toast_type[type] || UI.toast_type.info}`;
        el.textContent = message;
        document.getElementById("toasts").appendChild(el);
        setTimeout(() => {
            el.classList.add(...UI.toast_hide.split(" "));
            setTimeout(() => el.remove(), 300);
        }, timeout);
    }

    function reloadTable(selector) {
        if (!selector || !window.DataTable || !DataTable.isDataTable(selector)) return;
        $(selector).DataTable().ajax.reload(null, false); // keep the current page
    }

    async function openModal(url, options = {}) {
        context = options;
        const response = await fetch(url, {headers: {"X-Requested-With": "XMLHttpRequest"}});
        if (!response.ok) {
            toast(I18N.load_failed, "error");
            return;
        }
        modalBody.innerHTML = await response.text();
        modal.showModal();
        const first = modalBody.querySelector("input:not([type=hidden]), select, textarea");
        if (first) first.focus();
        document.dispatchEvent(new CustomEvent("app:modal-opened", {detail: {body: modalBody}}));
    }

    function closeModal() {
        modal.close();
        modalBody.innerHTML = "";
    }

    async function postForm(form) {
        const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: {"X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest"},
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }

    // Generic JSON POST, e.g. App.post("/api/pricing/calculate/", {...})
    async function post(url, data) {
        const response = await fetch(url, {
            method: "POST",
            body: JSON.stringify(data),
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }

    function onSuccess(data, ctx) {
        toast(data.message, "success");
        if (ctx.reload) {
            setTimeout(() => window.location.reload(), 600);
        } else {
            reloadTable(ctx.table);
        }
        document.dispatchEvent(new CustomEvent("app:saved", {detail: data}));
    }

    // ---- Event delegation ----

    function closeMenus(except) {
        document.querySelectorAll("[data-row-menu][data-open]").forEach((menu) => {
            if (menu !== except) menu.removeAttribute("data-open");
        });
        // <details data-dropdown> (e.g. the cost price breakdown) close like menus
        document.querySelectorAll("details[data-dropdown][open]").forEach((d) => {
            if (!except || !d.contains(except)) d.open = false;
        });
    }

    // Row action menu (3 dots): App.rowMenu([{label, url, table, danger}]); {label, href} is a plain link
    function rowMenu(items) {
        const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
        return `<div class="group/menu relative inline-block" data-row-menu>
            <button type="button" class="size-8 cursor-pointer rounded-md border border-transparent text-xl leading-none text-gray-500 hover:border-slate-200 hover:bg-slate-100 hover:text-gray-800 group-data-open/menu:border-slate-200 group-data-open/menu:bg-slate-100 group-data-open/menu:text-gray-800"
                data-menu-toggle aria-haspopup="true" aria-label="${esc(I18N.actions)}">&#8942;</button>
            <div class="absolute right-0 top-full z-50 mt-1 hidden min-w-37.5 rounded-lg border border-slate-200 bg-white p-1 shadow-xl group-data-open/menu:block" role="menu">
                ${items.map((i) => {
                    const cls = `block w-full cursor-pointer rounded-md px-3 py-2 text-left hover:bg-slate-100 ${i.danger ? "text-red-700" : "text-gray-800"}`;
                    return i.href
                        ? `<a role="menuitem" class="${cls}" href="${esc(i.href)}">${esc(i.label)}</a>`
                        : `<button type="button" role="menuitem" class="${cls}"
                            data-modal-url="${esc(i.url)}" ${i.table ? `data-table="${esc(i.table)}"` : ""}>${esc(i.label)}</button>`;
                }).join("")}
            </div>
        </div>`;
    }

    document.addEventListener("click", (event) => {
        const toggle = event.target.closest("[data-menu-toggle]");
        if (toggle) {
            const menu = toggle.closest("[data-row-menu]");
            closeMenus(menu);
            menu.toggleAttribute("data-open");
            return;
        }
        closeMenus(event.target);

        const opener = event.target.closest("[data-modal-url]");
        if (opener) {
            event.preventDefault();
            openModal(opener.dataset.modalUrl, {
                table: opener.dataset.table,
                reload: opener.hasAttribute("data-reload"),
            });
            return;
        }
        if (event.target.closest("[data-modal-close]")) {
            closeModal();
        }
    });

    // Close when clicking the backdrop
    modal.addEventListener("click", (event) => {
        if (event.target === modal) closeModal();
    });

    document.addEventListener("submit", async (event) => {
        const form = event.target;
        const inModal = form.classList.contains("modal-form");
        const ajaxForm = form.hasAttribute("data-ajax");
        if (!inModal && !ajaxForm) return;
        event.preventDefault();
        const submit = form.querySelector("[type=submit]");
        if (submit) submit.disabled = true;
        try {
            const data = await postForm(form);
            if (data.ok) {
                if (inModal) closeModal();
                onSuccess(data, inModal ? context : {
                    table: form.dataset.table,
                    reload: form.hasAttribute("data-reload"),
                });
            } else if (data.html && inModal) {
                modalBody.innerHTML = data.html; // form re-rendered with errors
                document.dispatchEvent(new CustomEvent("app:modal-opened", {detail: {body: modalBody}}));
            } else {
                toast(data.message || I18N.error, "error");
            }
        } catch (err) {
            toast(I18N.error, "error");
        } finally {
            if (submit) submit.disabled = false;
        }
    });

    // Sidebar toggle (collapse on desktop, slide-in on mobile); the sidebar's Tailwind variants react to these attributes.
    // The desktop collapsed state is remembered (restored by the inline script in base.html).
    const toggle = document.getElementById("sidebar-toggle");
    const sidebar = document.getElementById("sidebar");
    if (toggle && sidebar) {
        toggle.addEventListener("click", () => {
            const mobile = window.matchMedia("(width < 64rem)").matches; // Tailwind's lg breakpoint
            if (mobile) {
                sidebar.toggleAttribute("data-open");
                return;
            }
            const collapsed = sidebar.toggleAttribute("data-collapsed");
            try { localStorage.setItem("sidebar-collapsed", collapsed); } catch (err) { /* storage unavailable */ }
        });
    }

    // Django messages rendered by base.html
    (window.__flash || []).forEach((m) => toast(m.msg, m.type === "error" ? "error" : "success"));

    // Formatting helper shared by tables/calculator
    const eur = new Intl.NumberFormat("nl-NL", {style: "currency", currency: "EUR"});

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenus();
    });

    const badgeClass = (status) => UI.badge[status] || UI.badge.unknown;

    window.UI = UI;
    window.App = {csrfToken, toast, reloadTable, openModal, closeModal, post, rowMenu, badgeClass, formatEuro: (v) => eur.format(Number(v))};

    // Leaving a number box: clamp it to its min/max. Only bounds that are actually set count (a missing max
    // is "", which Number() turns into 0). Announce the change so autosave and live calculations see it.
    document.addEventListener("focusout", (event) => {
        const input = event.target;
        if (!(input instanceof HTMLInputElement) || input.type !== "number" || input.value === "") return;
        const value = Number(input.value);
        let clamped = value;
        if (input.min !== "" && value < Number(input.min)) clamped = Number(input.min);
        if (input.max !== "" && value > Number(input.max)) clamped = Number(input.max);
        if (clamped !== value) {
            input.value = clamped;
            input.dispatchEvent(new Event("input", {bubbles: true}));
        }
    });

    // <form data-enter-leaves-field>: Enter in a field only leaves that field instead of submitting the form
    // (the candidate page has several submit buttons; Enter would pick the first one, "Save as draft").
    document.addEventListener("keydown", (event) => {
        const field = event.target;
        if (event.key !== "Enter" || !field.form || !field.form.hasAttribute("data-enter-leaves-field")) return;
        if (field.tagName === "TEXTAREA" || field.type === "submit" || field.type === "button") return;
        event.preventDefault();
        field.blur();
    });
    document.querySelectorAll('input[type=range].slider').forEach(slider => {
      const number = document.getElementById(slider.dataset.sync);
      paintSlider(slider);
      if (!number) return;

      // slider -> number field
      slider.addEventListener('input', () => {
        number.value = slider.value;
        number.dispatchEvent(new Event('input', { bubbles: true })); // in case other code listens
        paintSlider(slider);
      });

      // number field -> slider
      const syncFromNumber = () => {
        if (number.value === '' || isNaN(number.valueAsNumber)) return; // don't jump while typing
        slider.value = number.value; // the browser clamps to min/max automatically
        paintSlider(slider);
      };
      number.addEventListener('input', syncFromNumber);
      number.addEventListener('change', syncFromNumber);
    });
})();
