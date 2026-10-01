from django.contrib import admin

from .models import Candidate


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ["full_name", "desired_role", "status", "expected_salary_month", "vacancy"]
    list_filter = ["status", "vacancy"]
    search_fields = ["first_name", "last_name", "email", "desired_role"]
