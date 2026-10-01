from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Candidate

# (legend, [field names]) rendered as <fieldset>s by core/_modal_form.html
FIELDSETS = [
    (_("Personal"), ["first_name", "last_name", "email", "phone", "city", "desired_role", "status", "vacancy"]),
    (_("Salary & hours"), ["expected_salary_month", "hours_per_week"]),
    (_("Travel & remote"), ["travel_known", "transport_type", "travel_distance_km", "remote_days_per_week"]),
    (_("Days off & benefits"), ["vacation_days", "sick_days_estimate", "secondary_benefits_month", "benefits_description"]),
    (_("Pricing"), ["cost_factor", "margin_per_hour", "proposed_rate"]),
    (_("Notes"), ["notes"]),
]


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [name for _legend, names in FIELDSETS for name in names]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3, "wide": True})}

    def fieldsets(self):
        return [(legend, [self[name] for name in names]) for legend, names in FIELDSETS]

    def clean(self):
        cleaned = super().clean()
        # TODO(Vidic): more validation (e.g. distance required when travel_known, hours vs remote days)
        if cleaned.get("travel_known") and not cleaned.get("travel_distance_km"):
            self.add_error("travel_distance_km", _("Required when travel details are known."))
        return cleaned
