from __future__ import annotations

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET

# ✅ 按你的实际模型改这里
from storageSystem.models import Device


# ============== 页面渲染 ==============

@require_GET
def index(request: HttpRequest) -> HttpResponse:
    """
    访问根路径 / 时，直接跳转到 /dashboard/
    """
    return redirect("dashboard")


@require_GET
def dashboard_page(request: HttpRequest) -> HttpResponse:
    """
    总览页面：统计 + 图表 + 表格
    """
    return render(request, "storageSystem/dashboard.html")


@require_GET
def coldroom_manage_page(request: HttpRequest) -> HttpResponse:
    """
    冷库数据管理页面
    """
    return render(request, "storageSystem/coldroom_manage.html")


@require_GET
def device_readings_page(request: HttpRequest, device_id: int) -> HttpResponse:
    """
    读取页面：展示某个设备的传感器数据页面
    URL 例如：/storage/device/13/readings/
    """
    device = get_object_or_404(Device, id=device_id)

    context = {
        "device": device,
        "base_id": request.GET.get("base_id", "").strip(),
    }
    return render(request, "storageSystem/device_readings.html", context)


# ============== 占位 API（可保留） ==============

@require_GET
def api_coldrooms_stats(request: HttpRequest) -> JsonResponse:
    """
    占位：GET /api/coldrooms/stats
    """
    return JsonResponse(
        {
            "total": 0,
            "normal": 0,
            "alarm": 0,
            "offline": 0,
            "ts": None,
        }
    )


@require_GET
def api_coldrooms_list(request: HttpRequest) -> JsonResponse:
    """
    占位：GET /api/coldrooms
    返回分页结构，rows 为空
    """
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1

    try:
        page_size = int(request.GET.get("pageSize", "10"))
    except ValueError:
        page_size = 10

    return JsonResponse(
        {
            "total": 0,
            "page": max(1, page),
            "pageSize": max(1, page_size),
            "rows": [],
        }
    )