from django import template

from core.ui import UI

register = template.Library()


@register.filter
def as_input(field):
    """Render a form field's widget with the shared Tailwind input classes."""
    if getattr(field.field.widget, "input_type", None) == "checkbox":
        classes = UI["checkbox"]
    else:
        classes = UI["input_error"] if field.errors else UI["input"]
    return field.as_widget(attrs={"class": classes})


@register.filter
def badge(status):
    """Budget status (ok | too_low | over | unknown) -> badge classes."""
    return UI["badge"].get(status, UI["badge"]["unknown"])
