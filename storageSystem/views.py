from django.shortcuts import render

# Create your views here.
# storageSystem/views.py
from __future__ import annotations

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET


# ============== 页面渲染（当前只需要这些） ==============

@require_GET
def index(request: HttpRequest) -> HttpResponse:
    """
    访问根路径 / 时，直接跳转到 /dashboard/
    （可选，但很实用，避免你手滑访问 / 看到 404）
    """
    return redirect("dashboard")


@require_GET
def dashboard_page(request: HttpRequest) -> HttpResponse:
    """
    总览页面：统计 + 图表 + 表格（目前仅渲染模板，不提供数据）
    """
    return render(request, "storageSystem/dashboard.html")


@require_GET
def coldroom_manage_page(request: HttpRequest) -> HttpResponse:
    """
    冷库数据管理页面（目前仅渲染模板，不提供数据）
    """
    return render(request, "storageSystem/coldroom_manage.html")


# ============== 下面是“以后接 API 时用”的占位（可删） ==============
# 如果你现在的前端 JS 已经写了 fetch('/api/...')，
# 那不写这些会在控制台看到 404。
# 你可以先用这些接口返回 mock/空数据，让页面不报错。
# 如果你不介意控制台 404，可以把下面全部删掉。


@require_GET
def api_coldrooms_stats(request: HttpRequest) -> JsonResponse:
    """
    占位：GET /api/coldrooms/stats
    现在先返回空统计，避免前端报错。
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
    返回分页结构，rows 为空。
    """
    # 前端可能会传 page/pageSize 等参数，这里简单兜底
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
