"""Shared Tailwind class strings (owner: Joseph).

The project has no custom CSS: everything is styled with Tailwind utility classes (loaded in base.html).
Components that are used in many templates *and* rendered from JavaScript are defined once here, so they
look the same everywhere:
  - templates: {{ ui.card }}, {{ ui.btn_primary }}, ... (core.context_processors.ui)
  - form fields: {{ field|as_input }}, budget badges: {{ status|badge }} ({% load ui %})
  - JavaScript: window.UI (json_script in base.html), e.g. UI.badge.over
One-off layout classes go straight into the template.
"""

_BTN = ("inline-flex cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-md border "
        "font-medium disabled:cursor-default disabled:opacity-60")
_BTN_MD = f"{_BTN} px-3.5 py-2"
_BTN_SM = f"{_BTN} px-2.5 py-1 text-[13px]"
_INPUT = ("w-full rounded-md border bg-white px-2.5 py-2 text-gray-800 "
          "focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/25")
_BADGE = "inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold"

UI = {
    # Surfaces & text
    "card": "rounded-lg border border-slate-200 bg-white p-5 shadow-sm",
    "h2": "mb-3.5 text-base font-bold",
    "section_label": "text-xs font-semibold uppercase tracking-wide text-gray-500",
    "icon_button": "inline-flex cursor-pointer p-1 text-2xl leading-none text-gray-500 hover:text-gray-800",

    # Buttons
    "btn_primary": f"{_BTN_MD} border-transparent bg-blue-600 text-white hover:bg-blue-700",
    "btn_primary_sm": f"{_BTN_SM} border-transparent bg-blue-600 text-white hover:bg-blue-700",
    "btn_secondary": f"{_BTN_MD} border-slate-200 bg-white text-gray-800 hover:bg-slate-100",
    "btn_edit": f"{_BTN_MD} border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100",
    "btn_danger": f"{_BTN_MD} border-transparent bg-red-700 text-white hover:bg-red-800",
    "btn_edit_sm": f"{_BTN_SM} border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100",
    "btn_danger_sm": f"{_BTN_SM} border-transparent bg-red-700 text-white hover:bg-red-800",

    # Form controls
    "input": f"{_INPUT} border-slate-200",
    "input_error": f"{_INPUT} border-red-700",
    "checkbox": "size-4 accent-blue-600",
    "number_box": ("flex items-center rounded-md border border-slate-200 bg-white "
                   "focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-600/25"),
    "number_box_input": "w-full min-w-0 bg-transparent px-2.5 py-2 text-right tabular-nums outline-none",
    "number_box_unit": "px-2.5 text-[13px] text-gray-500",

    # Budget status badges: ok = within budget, too_low = >10% under max, over = above max
    "badge": {
        "ok": f"{_BADGE} bg-green-100 text-green-700",
        "too_low": f"{_BADGE} bg-amber-100 text-amber-700",
        "over": f"{_BADGE} bg-red-100 text-red-700",
        "unknown": f"{_BADGE} bg-slate-100 text-gray-500",
    },

    # Simple key/value table (detail pages)
    "kv_table": "w-full border-collapse [&_td]:border-b [&_td]:border-dashed [&_td]:border-slate-200 [&_td]:py-1.75",
    "kv_value": "text-right font-semibold tabular-nums",

    # Card around a DataTable: let the row menu overflow the table, compact uppercase headers
    "dt_card": ("rounded-lg border border-slate-200 bg-white p-5 shadow-sm "
                "[&_.dt-container]:overflow-visible! [&_.dt-layout-table]:overflow-visible! [&_td]:overflow-visible! "
                "[&_td]:align-middle [&_thead_th]:text-xs [&_thead_th]:uppercase [&_thead_th]:tracking-wide "
                "[&_thead_th]:text-gray-500 [&_.dt-search_input]:w-60!"),

    # Modal partials (core/_modal_form.html, core/_confirm_delete.html)
    "modal_header": "flex items-center justify-between border-b border-slate-200 px-5.5 py-4.5",
    "modal_title": "text-[17px] font-bold",
    "modal_content": "max-h-[calc(90vh-140px)] overflow-y-auto px-5.5 py-5",
    "modal_footer": "flex justify-end gap-2.5 border-t border-slate-200 bg-slate-50 px-5.5 py-3.5",

    # Pricing summary: cost + travel + margin = tariff
    "sum_grid": "flex flex-wrap items-stretch gap-2.5",
    "sum_item": "flex min-w-27.5 flex-1 flex-col gap-1 rounded-lg bg-slate-100 px-3.5 py-3",
    "sum_label": "text-xs text-gray-500",
    "sum_value": "text-lg font-bold tabular-nums",
    "sum_total": "flex min-w-27.5 flex-1 flex-col gap-1 rounded-lg bg-slate-900 px-3.5 py-3 text-white",
    "sum_total_label": "text-xs text-slate-300",
    "sum_total_value": "text-[26px] font-bold tabular-nums",
    "sum_op": "self-center text-xl font-bold text-gray-500",

    # Result tile that opens a dropdown with the calculation steps
    # (pricing/_steps_tile.html, pricing/_steps.html and renderSteps() in calculator.js)
    "steps_tile": ("flex h-full cursor-pointer list-none flex-col gap-1 rounded-lg bg-slate-100 px-3.5 py-3 "
                   "hover:bg-slate-200 group-open/steps:bg-slate-200 [&::-webkit-details-marker]:hidden"),
    "steps_tile_total": ("flex h-full cursor-pointer list-none flex-col gap-1 rounded-lg bg-slate-900 px-3.5 py-3 "
                         "text-white hover:bg-slate-800 group-open/steps:bg-slate-800 [&::-webkit-details-marker]:hidden"),
    "steps_dropdown": ("absolute left-0 top-full z-30 mt-1.5 w-72 max-w-[calc(100vw-3rem)] rounded-lg border "
                       "border-slate-200 bg-white px-3.5 py-2.5 text-[13px] text-gray-800 shadow-lg"),
    "step_row": "flex items-baseline gap-2 py-1",
    "step_result_row": "flex items-baseline gap-2 py-1 font-semibold last:mt-1 last:border-t last:border-slate-200 last:pt-2",
    "step_op": "w-3 shrink-0 text-center text-gray-400",
    "step_detail": "ml-1 text-xs font-normal text-gray-400",
    "step_value": "ml-auto whitespace-nowrap tabular-nums",

    # Toasts (top-left), created by App.toast() in app.js
    "toast": ("min-w-65 max-w-95 rounded-lg px-4 py-3 font-medium text-white shadow-lg transition duration-300 "
              "starting:-translate-x-5 starting:opacity-0"),
    "toast_hide": "-translate-x-5 opacity-0",
    "toast_type": {
        "success": "bg-green-700",
        "error": "bg-red-700",
        "warning": "bg-amber-700",
        "info": "bg-slate-900",
    },
}
