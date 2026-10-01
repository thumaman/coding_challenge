"""Root URL configuration. Each app owns its own urls.py (see docs/PLAN.md)."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("candidates/", include("candidates.urls")),
    path("clients/", include("clients.urls")),
    path("employees/", include("admin_page.urls")),
    path("", include("pricing.urls")),
    path("", include("core.urls")),
]
