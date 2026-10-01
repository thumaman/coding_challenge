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
    # Clients (companies)
    path("", views.client_list, name="client_list"),
    # AI advisor
    path("advisor/<int:candidate_pk>/apply/", views.apply_tweak, name="apply_tweak"),
]
