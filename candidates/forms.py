from django import forms
from django.utils.translation import gettext_lazy as _

from clients.models import Vacancy
from pricing import constants as C

from .models import Candidate, CandidateVacancy


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [
            "first_name", "last_name", "email", "phone", "city", "desired_role", "status",
            "expected_salary_month", "hours_per_week", "transport_type", "remote_days_per_week",
            "cost_factor", "margin_per_hour", "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "wide": True}),
            "margin_per_hour": forms.NumberInput(attrs={"min": C.MIN_MARGIN, "max": C.MAX_MARGIN, "step": "0.5"}),
            "cost_factor": forms.NumberInput(attrs={"step": "0.05"}),
            "remote_days_per_week": forms.NumberInput(attrs={"min": 0, "max": 5}),
            # Hooks for calculator.js on the candidate page (live distance + tariff)
            "city": forms.TextInput(attrs={"data-role": "home"}),
        }


class CandidateVacancyForm(forms.ModelForm):
    """One vacancy the candidate is considered for (a row on the candidate page)."""

    class Meta:
        model = CandidateVacancy
        fields = ["vacancy", "status", "client_pays_travel", "travel_distance_km", "proposed_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vacancy"].queryset = Vacancy.objects.select_related("client")

    def save_link(self, candidate, city_changed=False):
        """Save this row for `candidate`. The distance is calculated automatically, unless typed in by hand."""
        link = super().save(commit=False)
        link.candidate = candidate
        location_changed = city_changed or "vacancy" in self.changed_data
        if "travel_distance_km" not in self.changed_data and (location_changed or link.travel_distance_km is None):
            link.refresh_travel_distance()
        link.save()
        return link


class BaseCandidateVacancyFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        kept = [f for f in self.forms if f.cleaned_data.get("vacancy") and not self._should_delete_form(f)]
        if not kept:
            raise forms.ValidationError(_("Choose at least one vacancy."))
        vacancies = [f.cleaned_data["vacancy"] for f in kept]
        if len(set(vacancies)) != len(vacancies):
            raise forms.ValidationError(_("Each vacancy can only be added once."))

    def save_links(self, city_changed=False):
        for form in self.deleted_forms:
            if form.instance.pk:
                form.instance.delete()
        for form in self.forms:
            if form in self.deleted_forms or not form.cleaned_data.get("vacancy"):
                continue
            if form.has_changed() or city_changed or form.instance.pk is None:
                form.save_link(self.instance, city_changed=city_changed)


CandidateVacancyFormSet = forms.inlineformset_factory(
    Candidate, CandidateVacancy, form=CandidateVacancyForm, formset=BaseCandidateVacancyFormSet,
    extra=0, can_delete=True,
)
