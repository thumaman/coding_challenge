from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    path("calculator/", views.calculator, name="calculator"),
    path("api/pricing/calculate/", views.calculate_api, name="calculate"),
    path("api/pricing/reverse/", views.reverse_api, name="reverse"),
]
