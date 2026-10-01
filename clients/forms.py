from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Client, Vacancy


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "industry", "city", "contact_name", "contact_email"]


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = [
            "client", "title", "address", "city", "max_rate_per_hour", "client_pays_travel", "hours_per_week",
            "remote_days_allowed", "min_salary", "max_salary", "skills", "is_open",
        ]
        widgets = {"skills": forms.Textarea(attrs={"rows": 2, "wide": True})}

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("min_salary"), cleaned.get("max_salary")
        if low and high and low > high:
            self.add_error("max_salary", _("Max salary must be higher than min salary."))
        if (cleaned.get("remote_days_allowed") or 0) > 5:
            self.add_error("remote_days_allowed", _("At most 5 days."))
        return cleaned
