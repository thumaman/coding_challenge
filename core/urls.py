from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="candidates:list"), name="home"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
]
