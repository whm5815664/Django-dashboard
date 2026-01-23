from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def dashboard_page(request):
    return render(request, "storageSystem/dashboard.html")


@require_GET
def coldroom_manage_page(request):
    return render(request, "storageSystem/coldroom_manage.html")
