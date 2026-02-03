from django.core.paginator import Paginator
from django.db.models import Q
from storageSystem.models import Device


def get_devices_page(
    page: int,
    page_size: int,
    *,
    base_id: str = "",
    status: str = "",
    keyword: str = "",
):
    """
    按基地（base_id）分页获取设备列表。
    """
    qs = Device.objects.select_related("base").all().order_by("-last_seen", "-id")

    if base_id:
        qs = qs.filter(base__base_id=base_id)

    if status:
        qs = qs.filter(status=status)

    if keyword:
        k = keyword.strip()
        qs = qs.filter(Q(name__icontains=k) | Q(code__icontains=k) | Q(location__icontains=k))

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    rows = []
    for d in page_obj.object_list:
        rows.append(
            {
                "id": d.id,
                "name": d.name,
                "code": d.code,
                "base_id": d.base.base_id,
                "location": d.location,
                "status": d.status,
                "last_seen": d.last_seen.strftime("%Y-%m-%d %H:%M:%S") if d.last_seen else "",
            }
        )

    return {
        "total": paginator.count,
        "page": page_obj.number,
        "pageSize": page_size,
        "rows": rows,
    }
