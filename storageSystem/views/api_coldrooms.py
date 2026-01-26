from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def devices(request):
    # TODO: 后续改成从数据库查询 + 分页 + 筛选
    return JsonResponse({
        "total": 0,
        "page": int(request.GET.get("page", 1)),
        "pageSize": int(request.GET.get("pageSize", 10)),
        "rows": [],
    })
