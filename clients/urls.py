from django.urls import path

from . import views

app_name = "clients"

urlpatterns = [
    # Vacancies
    path("vacancies/", views.vacancy_list, name="vacancy_list"),
    path("vacancies/data/", views.vacancy_data, name="data"),
    path("vacancies/new/", views.VacancyCreateView.as_view(), name="create"),
    path("vacancies/<int:pk>/", views.vacancy_detail, name="detail"),
    path("vacancies/<int:pk>/edit/", views.VacancyUpdateView.as_view(), name="update"),
    path("vacancies/<int:pk>/delete/", views.VacancyDeleteView.as_view(), name="delete"),
    path("vacancies/drafts/", views.vacancy_draft_list, name="drafts"),
    path("vacancies/drafts/autosave/", views.vacancy_draft_autosave, name="draft_autosave"),
    path("vacancies/drafts/<int:pk>/delete/", views.VacancyDraftDeleteView.as_view(), name="draft_delete"),
    # Clients (companies)
    path("", views.client_list, name="client_list"),
    path("new/", views.ClientCreateView.as_view(), name="client_create"),
    path("<int:pk>/edit/", views.ClientUpdateView.as_view(), name="client_update"),
    path("<int:pk>/delete/", views.ClientDeleteView.as_view(), name="client_delete"),
    # AI advisor
    path("advisor/link/<int:link_pk>/apply/", views.apply_tweak, name="apply_tweak"),
]
