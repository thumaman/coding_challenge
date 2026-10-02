// New-candidate and new-vacancy pages: keep unfinished work as a draft (see core/drafts.py).
// Saves shortly after typing stops, and once more when the tab is hidden, closed or left
// (keepalive lets that last request finish after the page is gone).
// Nothing is saved until the recruiter changes something; submitting the form skips the final save.
(function () {
    "use strict";

    const form = document.querySelector("form[data-autosave]");
    const url = form && form.dataset.autosave;
    if (!url) return;
    const draftInput = form.querySelector("[name=draft]");
    const status = document.getElementById("draft-status");
    const T = window.DRAFT_I18N || {saved: "Draft saved"};
    let dirty = false;
    let submitting = false;
    let timer;

    function payload() {
        const data = new FormData(form);
        data.delete("action");
        return data;
    }

    function remember(id) {
        draftInput.value = id;
        const params = new URLSearchParams(window.location.search);
        params.set("draft", id);
        history.replaceState(null, "", `${window.location.pathname}?${params}`);
    }

    // One request at a time, so the first save's draft id is known before the next one is sent
    let queue = Promise.resolve();
    function save() {
        clearTimeout(timer);
        queue = queue.then(send);
        return queue;
    }

    async function send() {
        if (!dirty || submitting) return;
        dirty = false;
        try {
            const response = await fetch(url, {
                method: "POST", body: payload(), keepalive: true, headers: {"X-CSRFToken": App.csrfToken()},
            });
            const data = await response.json();
            if (!data.ok) throw new Error();
            remember(data.id);
            const time = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
            if (status) status.textContent = `${T.saved} ${time}`;
        } catch (err) {
            dirty = true; // try again with the next change or when the page is left
        }
    }

    function changed() {
        dirty = true;
        clearTimeout(timer);
        timer = setTimeout(save, 1500);
    }

    form.addEventListener("input", changed);
    // "change" fires when an edited field is left (or a select/radio is picked): save right away
    form.addEventListener("change", () => { dirty = true; save(); });
    form.addEventListener("submit", () => { submitting = true; clearTimeout(timer); });
    window.addEventListener("pagehide", save);
    window.Draft = {save: () => { dirty = true; return save(); }}; // e.g. before leaving via a link
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") save(); });
})();
