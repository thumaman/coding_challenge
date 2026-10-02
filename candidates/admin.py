from django.contrib import admin

from .models import Candidate, CandidateDraft, CandidateVacancy


class CandidateVacancyInline(admin.TabularInline):
    model = CandidateVacancy
    extra = 0
    autocomplete_fields = ["vacancy"]


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ["full_name", "desired_role", "status", "expected_salary_month"]
    list_filter = ["status", "vacancies"]
    search_fields = ["first_name", "last_name", "email", "desired_role"]
    inlines = [CandidateVacancyInline]


@admin.register(CandidateDraft)
class CandidateDraftAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "updated_at"]
