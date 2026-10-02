from django.contrib import admin

from .models import Client, Vacancy, VacancyDraft


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "industry", "city", "contact_name"]
    search_fields = ["name"]


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ["title", "client", "max_rate_per_hour", "hours_per_week", "is_open"]
    list_filter = ["is_open", "client"]
    search_fields = ["title", "client__name"]


@admin.register(VacancyDraft)
class VacancyDraftAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "updated_at"]
