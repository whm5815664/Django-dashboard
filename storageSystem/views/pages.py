from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET

from storageSystem.models import Device


@require_GET
def index(request: HttpRequest) -> HttpResponse:
    return redirect("dashboard")


@require_GET
def dashboard_page(request: HttpRequest) -> HttpResponse:
    return render(request, "storageSystem/dashboard.html")


@require_GET
def coldroom_manage_page(request: HttpRequest) -> HttpResponse:
    return render(request, "storageSystem/coldroom_manage.html")


@require_GET
def device_readings_page(request: HttpRequest, device_id: int) -> HttpResponse:
    device = get_object_or_404(Device.objects.using("pig"), pk=device_id)

    context = {
        "device": device,
        "base_id": (request.GET.get("base_id") or "").strip(),
    }
    return render(request, "storageSystem/device_readings.html", context)