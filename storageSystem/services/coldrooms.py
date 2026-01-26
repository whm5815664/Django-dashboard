from django.core.paginator import Paginator
from django.db.models import Q
from storageSystem.models import Device


def get_devices_page(
    page: int,
    page_size: int,
    *,
    cold_room: str = "",
    status: str = "",
    keyword: str = "",
):
    qs = Device.objects.select_related("cold_room").all().order_by("-last_seen", "-id")

    if cold_room:
        qs = qs.filter(cold_room__name=cold_room)

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
                "cold_room": d.cold_room.name,
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
