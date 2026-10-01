from django.utils.translation import gettext_lazy as _

from .ui import UI

# Sidebar entries: (url name, label, icon key, view-name prefix that marks the item active)
NAV_ITEMS = [
    ("core:dashboard", _("Dashboard"), "home", "core:dashboard"),
    ("candidates:list", _("Candidates"), "users", "candidates:"),
    ("clients:vacancy_list", _("Vacancies"), "briefcase", "clients:vacancy"),
    ("clients:client_list", _("Clients"), "building", "clients:client"),
    ("pricing:calculator", _("Calculator"), "calc", "pricing:"),
]


def navigation(request):
    match = getattr(request, "resolver_match", None)
    current = match.view_name if match else ""
    return {
        "nav_items": [
            {
                "url_name": url_name,
                "label": label,
                "icon": icon,
                "active": current.startswith(prefix),
            }
            for url_name, label, icon, prefix in NAV_ITEMS
        ]
    }


def ui(request):
    return {"ui": UI}
