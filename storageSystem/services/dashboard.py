from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from storageSystem.models import Device, Alarm


def get_stats():
    total = Device.objects.count()
    online = Device.objects.filter(status="online").count()
    offline = Device.objects.filter(status="offline").count()
    alarm_devices = Device.objects.filter(status="alarm").count()
    active_alarm = Alarm.objects.filter(is_active=True).count()

    return {
        "total": total,
        "online": online,
        "offline": offline,
        "alarm_devices": alarm_devices,
        "active_alarm": active_alarm,
        "ts": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_trend(days: int = 7):
    days = 7 if days not in (7, 30) else days

    end = timezone.now()
    start = end - timedelta(days=days - 1)

    # 示例：按天统计告警数（你也可以换成在线/离线变化）
    qs = (
        Alarm.objects.filter(created_at__date__gte=start.date(), created_at__date__lte=end.date())
        .annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(cnt=Count("id"))
        .order_by("d")
    )

    x = [item["d"].strftime("%Y-%m-%d") for item in qs]
    y = [item["cnt"] for item in qs]

    return {
        "x": x,
        "series": [
            {"name": "告警数量", "data": y},
        ],
    }
