/*
 * Shared front-end helpers (owner: Joseph). See docs/PLAN.md, "Shared contracts".
 *
 * Declarative usage, no page JS needed:
 *   <button data-modal-url="/candidates/new/" data-table="#candidates">+ Add</button>
 *
 * The modal partial must contain a <form class="modal-form">. On submit it is POSTed with fetch.
 * The server answers {ok: true, message} or {ok: false, html}. On success the modal closes, a toast
 * is shown top-left, and the DataTable named in data-table is reloaded (or the page, with data-reload).
 */
(function () {
    "use strict";

    const I18N = Object.assign({
        actions: "Actions",
        load_failed: "Could not load the form.",
        error: "Something went wrong. Please try again.",
    }, window.APP_I18N || {});
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
        el.className = `toast toast-${type}`;
        el.textContent = message;
        document.getElementById("toasts").appendChild(el);
        setTimeout(() => {
            el.classList.add("hide");
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
        document.querySelectorAll(".row-menu.open").forEach((menu) => {
            if (menu !== except) menu.classList.remove("open");
        });
    }

    // Row action menu (3 dots): App.rowMenu([{label, url, table, danger}])
    function rowMenu(items) {
        const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
        return `<div class="row-menu">
            <button type="button" class="row-menu-toggle" data-menu-toggle aria-haspopup="true" aria-label="${esc(I18N.actions)}">&#8942;</button>
            <div class="row-menu-items" role="menu">
                ${items.map((i) => `<button type="button" role="menuitem" class="${i.danger ? "danger" : ""}"
                    data-modal-url="${esc(i.url)}" ${i.table ? `data-table="${esc(i.table)}"` : ""}>${esc(i.label)}</button>`).join("")}
            </div>
        </div>`;
    }

    document.addEventListener("click", (event) => {
        const toggle = event.target.closest("[data-menu-toggle]");
        if (toggle) {
            const menu = toggle.closest(".row-menu");
            closeMenus(menu);
            menu.classList.toggle("open");
            return;
        }
        closeMenus();

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

    // Sidebar toggle (collapse on desktop, slide-in on mobile)
    const toggle = document.getElementById("sidebar-toggle");
    if (toggle) {
        toggle.addEventListener("click", () => {
            const mobile = window.matchMedia("(max-width: 900px)").matches;
            document.body.classList.toggle(mobile ? "sidebar-open" : "sidebar-collapsed");
        });
    }

    // Django messages rendered by base.html
    (window.__flash || []).forEach((m) => toast(m.msg, m.type === "error" ? "error" : "success"));

    // Formatting helper shared by tables/calculator
    const eur = new Intl.NumberFormat("nl-NL", {style: "currency", currency: "EUR"});

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenus();
    });

    window.App = {csrfToken, toast, reloadTable, openModal, closeModal, post, rowMenu, formatEuro: (v) => eur.format(Number(v))};
})();
