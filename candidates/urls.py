from django.urls import path

from . import views

app_name = "candidates"

urlpatterns = [
    path("", views.candidate_list, name="list"),
    path("data/", views.candidate_data, name="data"),
    path("new/", views.CandidateCreateView.as_view(), name="create"),
    path("<int:pk>/", views.candidate_detail, name="detail"),
    path("<int:pk>/edit/", views.CandidateUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.CandidateDeleteView.as_view(), name="delete"),
    path("drafts/", views.draft_list, name="drafts"),
    path("drafts/autosave/", views.draft_autosave, name="draft_autosave"),
    path("drafts/<int:pk>/delete/", views.CandidateDraftDeleteView.as_view(), name="draft_delete"),
]
