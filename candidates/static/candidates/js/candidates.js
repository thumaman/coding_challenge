// Candidate form behaviour (owner: Vidic): travel fields only when travel details are known.
document.addEventListener("app:modal-opened", ({detail}) => {
    const toggle = detail.body.querySelector("[name=travel_known]");
    if (!toggle) return;
    const travelFields = ["transport_type", "travel_distance_km"].map(
        (name) => detail.body.querySelector(`[data-field=${name}]`)
    );
    const sync = () => travelFields.forEach((el) => el && (el.hidden = !toggle.checked));
    toggle.addEventListener("change", sync);
    sync();
});
