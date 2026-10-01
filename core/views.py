from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache


@login_not_required
def manifest(request):
    return render(request, "core/manifest.webmanifest", content_type="application/manifest+json")


@login_not_required
@never_cache
def service_worker(request):
    # Served from the site root so the service worker can control every page.
    response = render(request, "core/sw.js", content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response
