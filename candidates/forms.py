from django import forms
from django.utils.translation import gettext_lazy as _

from pricing import constants as C

from .models import Candidate

# (legend, [field names]) rendered as <fieldset>s by core/_modal_form.html
FIELDSETS = [
    (_("Personal"), ["first_name", "last_name", "email", "phone", "city", "desired_role", "status", "vacancy"]),
    (_("Salary & hours"), ["expected_salary_month", "hours_per_week"]),
    (_("Travel"), ["transport_type", "travel_distance_km", "remote_days_per_week"]),
    (_("Pricing"), ["cost_factor", "margin_per_hour", "proposed_rate"]),
    (_("Notes"), ["notes"]),
]


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [name for _legend, names in FIELDSETS for name in names]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "wide": True}),
            "margin_per_hour": forms.NumberInput(attrs={"min": C.MIN_MARGIN, "max": C.MAX_MARGIN, "step": "0.5"}),
            "cost_factor": forms.NumberInput(attrs={"step": "0.05"}),
        }

    def fieldsets(self):
        return [(legend, [self[name] for name in names]) for legend, names in FIELDSETS]

    def save(self, commit=True):
        candidate = super().save(commit=False)
        # Distance is calculated automatically, unless the recruiter typed one in themselves
        location_changed = {"city", "vacancy"} & set(self.changed_data)
        if "travel_distance_km" not in self.changed_data and (location_changed or candidate.travel_distance_km is None):
            candidate.refresh_travel_distance()
        if commit:
            candidate.save()
        return candidate
