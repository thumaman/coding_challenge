from django.contrib import admin

from .models import Candidate, CandidateDraft


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ["full_name", "desired_role", "status", "expected_salary_month", "vacancy"]
    list_filter = ["status", "vacancy"]
    search_fields = ["first_name", "last_name", "email", "desired_role"]


@admin.register(CandidateDraft)
class CandidateDraftAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "updated_at"]
