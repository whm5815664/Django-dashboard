import re
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Max
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from storageSystem.models import Device

from ..models import Base, EnvironmentData


def _now() -> timezone.datetime:
    """返回当前时间（带时区）。"""
    return timezone.now()


def _base_id_to_pigsty_id(base_id: str) -> Optional[int]:
    """将基地编号（如 HB001）映射为远程库 pigsty_id（取数字部分转 int）。"""
    m = re.search(r"(\d+)", str(base_id or ""))
    return int(m.group(1)) if m else None


def _is_abnormal(
    temperature: Optional[float],
    humidity: Optional[float],
    *,
    temp_min: float = 0,
    temp_max: float = 45,
    hum_min: float = 20,
    hum_max: float = 95,
) -> Tuple[bool, List[str]]:
    """温湿度阈值告警判定，返回 (是否异常, 原因列表)。"""
    reasons: List[str] = []
    if temperature is not None and (temperature < temp_min or temperature > temp_max):
        reasons.append(f"温度异常({temperature:.1f}°C)")
    if humidity is not None and (humidity < hum_min or humidity > hum_max):
        reasons.append(f"湿度异常({humidity:.0f}%)")
    return (len(reasons) > 0), reasons


def _get_float_query(request, key: str, default: float) -> float:
    try:
        v = request.GET.get(key)
        if v is None or str(v).strip() == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _get_latest_env_map() -> Dict[int, Dict[str, Any]]:
    """按 pigsty_id 获取最新一条环境数据，返回 {pigsty_id: record}。"""
    latest = (
        EnvironmentData.objects.using("pig")
        .values("pigsty_id")
        .annotate(latest_time=Max("collected_time"))
    )
    latest_map = {
        row["pigsty_id"]: row["latest_time"]
        for row in latest
        if row.get("pigsty_id") is not None and row.get("latest_time") is not None
    }

    out: Dict[int, Dict[str, Any]] = {}
    for pigsty_id, latest_time in latest_map.items():
        rec = (
            EnvironmentData.objects.using("pig")
            .filter(pigsty_id=pigsty_id, collected_time=latest_time)
            .values("pigsty_id", "device_id", "temperature", "humidity", "collected_time")
            .order_by("-id")
            .first()
        )
        if rec:
            out[int(pigsty_id)] = rec
    return out


def _get_device_online_stats() -> Tuple[int, int]:
    """从远程库 pig.device 统计 (总设备数, 在线设备数)。description 为空/NULL 视为不在线。"""
    total = Device.objects.using("pig").count()
    online = (
        Device.objects.using("pig")
        .exclude(description__isnull=True)
        .exclude(description="")
        .count()
    )
    return total, online


@require_GET
def dashboard_summary(request):
    """顶部 KPI：在线基地数 / 设备在线数 / 异常警告数。"""
    online_window_min = int(request.GET.get("online_window_min") or 30)
    online_cutoff = _now() - timedelta(minutes=online_window_min)
    temp_min = _get_float_query(request, "temp_min", 0)
    temp_max = _get_float_query(request, "temp_max", 45)
    hum_min = _get_float_query(request, "hum_min", 20)
    hum_max = _get_float_query(request, "hum_max", 95)
    if temp_min > temp_max:
        temp_min, temp_max = temp_max, temp_min
    if hum_min > hum_max:
        hum_min, hum_max = hum_max, hum_min

    base_total = Base.objects.count()
    latest_env = _get_latest_env_map()

    online_base_count = 0
    abnormal_warning_count = 0
    for rec in latest_env.values():
        ts = rec.get("collected_time")
        if ts and ts >= online_cutoff:
            online_base_count += 1
        abnormal, _ = _is_abnormal(
            rec.get("temperature"),
            rec.get("humidity"),
            temp_min=temp_min,
            temp_max=temp_max,
            hum_min=hum_min,
            hum_max=hum_max,
        )
        if abnormal:
            abnormal_warning_count += 1

    try:
        device_total, online_device_count = _get_device_online_stats()
    except Exception:
        device_total, online_device_count = 0, 0

    return JsonResponse(
        {
            "success": True,
            "base_total": base_total,
            "online_base_count": online_base_count,
            "device_total": device_total,
            "online_device_count": online_device_count,
            "abnormal_warning_count": abnormal_warning_count,
            "online_window_min": online_window_min,
        }
    )


@require_GET
def dashboard_overview_matrix(request):
    """总览矩阵：按基地列出最新温湿度与状态。"""
    temp_min = _get_float_query(request, "temp_min", 0)
    temp_max = _get_float_query(request, "temp_max", 45)
    hum_min = _get_float_query(request, "hum_min", 20)
    hum_max = _get_float_query(request, "hum_max", 95)
    if temp_min > temp_max:
        temp_min, temp_max = temp_max, temp_min
    if hum_min > hum_max:
        hum_min, hum_max = hum_max, hum_min

    bases = list(
        Base.objects.values(
            "base_id",
            "base_name",
            "longitude",
            "latitude",
            "province_name",
            "city_name",
        ).order_by("base_id")
    )
    latest_env = _get_latest_env_map()

    items: List[Dict[str, Any]] = []
    for b in bases:
        pigsty_id = _base_id_to_pigsty_id(b["base_id"])
        rec = latest_env.get(pigsty_id) if pigsty_id is not None else None

        temp = None if not rec else rec.get("temperature")
        hum = None if not rec else rec.get("humidity")
        collected_time = None if not rec else rec.get("collected_time")

        if rec is None:
            status, reasons = "无数据", []
        else:
            abnormal, reasons = _is_abnormal(
                temp,
                hum,
                temp_min=temp_min,
                temp_max=temp_max,
                hum_min=hum_min,
                hum_max=hum_max,
            )
            status = "异常" if abnormal else "正常"

        items.append(
            {
                "base_id": b["base_id"],
                "base_name": b["base_name"],
                "longitude": b.get("longitude"),
                "latitude": b.get("latitude"),
                "province_name": b.get("province_name"),
                "city_name": b.get("city_name"),
                "pigsty_id": pigsty_id,
                "temperature": temp,
                "humidity": hum,
                "collected_time": collected_time,
                "status": status,
                "reasons": reasons,
            }
        )

    return JsonResponse({"success": True, "items": items})


@require_GET
def dashboard_base_env(request):
    """基地环境数据：按基地返回最新 N 条环境数据（强制最多 20）。"""
    base_id = (request.GET.get("base_id") or "").strip()
    pigsty_id = _base_id_to_pigsty_id(base_id)
    if pigsty_id is None:
        return JsonResponse({"success": False, "error": "base_id 无法映射到 pigsty_id"}, status=400)

    try:
        limit = int(request.GET.get("limit") or 20)
    except Exception:
        limit = 20
    limit = max(1, min(limit, 20))

    qs = (
        EnvironmentData.objects.using("pig")
        .filter(pigsty_id=pigsty_id)
        .order_by("-collected_time", "-id")
        .values(
            "temperature",
            "humidity",
            "CO2",
            "VOC",
            "H2",
            "C2H4",
            "C2H5OH",
            "device_id",
            "collected_time",
        )[:limit]
    )
    return JsonResponse({"success": True, "base_id": base_id, "pigsty_id": pigsty_id, "items": list(qs)})


@require_GET
def dashboard_today_series(request):
    """今日温湿度折线图：返回选中基地当日 00:00~24:00 的温湿度序列。"""
    base_id = (request.GET.get("base_id") or "").strip()
    pigsty_id = _base_id_to_pigsty_id(base_id)
    if pigsty_id is None:
        return JsonResponse({"success": False, "error": "base_id 无法映射到 pigsty_id"}, status=400)

    now_local = timezone.localtime(_now())
    today = now_local.date()
    start_local = timezone.make_aware(datetime.combine(today, time.min), now_local.tzinfo)
    end_local = start_local + timedelta(days=1)

    qs = (
        EnvironmentData.objects.using("pig")
        .filter(pigsty_id=pigsty_id, collected_time__gte=start_local, collected_time__lt=end_local)
        .order_by("collected_time", "id")
        .values("collected_time", "temperature", "humidity")[:8000]
    )

    return JsonResponse({"success": True, "base_id": base_id, "pigsty_id": pigsty_id, "date": str(today), "items": list(qs)})


@require_GET
def dashboard_alarm_center(request):
    """协同预警中心：扫描各基地最新温湿度，输出异常告警列表。"""
    temp_min = _get_float_query(request, "temp_min", 0)
    temp_max = _get_float_query(request, "temp_max", 45)
    hum_min = _get_float_query(request, "hum_min", 20)
    hum_max = _get_float_query(request, "hum_max", 95)

    # 兜底：避免 min/max 填反导致全部异常/全部正常
    if temp_min > temp_max:
        temp_min, temp_max = temp_max, temp_min
    if hum_min > hum_max:
        hum_min, hum_max = hum_max, hum_min

    bases = list(Base.objects.values("base_id", "base_name"))
    base_by_pigsty: Dict[int, Dict[str, Any]] = {}
    for b in bases:
        pid = _base_id_to_pigsty_id(b["base_id"])
        if pid is not None:
            base_by_pigsty[pid] = b

    latest_env = _get_latest_env_map()
    alarms: List[Dict[str, Any]] = []
    for pigsty_id, rec in latest_env.items():
        abnormal, reasons = _is_abnormal(
            rec.get("temperature"),
            rec.get("humidity"),
            temp_min=temp_min,
            temp_max=temp_max,
            hum_min=hum_min,
            hum_max=hum_max,
        )
        if not abnormal:
            continue
        b = base_by_pigsty.get(int(pigsty_id))
        alarms.append(
            {
                "level": "warning",
                "base_id": (b or {}).get("base_id") or str(pigsty_id),
                "base_name": (b or {}).get("base_name") or str(pigsty_id),
                "device_id": rec.get("device_id"),
                "temperature": rec.get("temperature"),
                "humidity": rec.get("humidity"),
                "collected_time": rec.get("collected_time"),
                "message": "，".join(reasons),
            }
        )

    alarms.sort(key=lambda x: x.get("collected_time") or _now(), reverse=True)
    return JsonResponse({"success": True, "items": alarms[:50]})


@require_GET
def dashboard_device_status(request):
    """设备运行状况：返回在线率（远程库 pig.device，description 非空视为在线）。"""
    try:
        total_devices, online_devices = _get_device_online_stats()
    except Exception:
        total_devices, online_devices = 0, 0

    online_rate = 0 if total_devices == 0 else round(online_devices * 100 / total_devices, 1)
    return JsonResponse({"success": True, "total_devices": total_devices, "online_devices": online_devices, "online_rate": online_rate})


@require_GET
def dashboard_base_monitor_images(request):
    """当前基地 environment_data 中带图片路径的最新 4 条（设备监控图）。"""
    base_id = (request.GET.get("base_id") or "").strip()
    pigsty_id = _base_id_to_pigsty_id(base_id)
    if pigsty_id is None:
        return JsonResponse({"success": False, "error": "base_id 无法映射到 pigsty_id"}, status=400)

    qs = (
        EnvironmentData.objects.using("pig")
        .filter(pigsty_id=pigsty_id)
        .exclude(image__isnull=True)
        .exclude(image="")
        .order_by("-collected_time", "-id")
        .values("image", "device_id", "collected_time")[:4]
    )
    items: List[Dict[str, Any]] = []
    for row in qs:
        path = (row.get("image") or "").strip()
        if not path:
            continue
        items.append(
            {
                "image_path": path,
                "device_id": row.get("device_id"),
                "collected_time": row.get("collected_time"),
            }
        )
    return JsonResponse({"success": True, "base_id": base_id, "pigsty_id": pigsty_id, "items": items})
