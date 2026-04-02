# storageSystem/views/api_dashboard.py
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import json
import traceback

from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator
from django.db import connections, models, transaction
from django.db.models import Q, Count, Max, OuterRef, Subquery
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from storageSystem.models import Base, Device, DeviceReading

REMOTE_DB = "pig"
MEDIA_BASE_URL = "http://47.99.61.189:8175/media/"


def _json_ok(data: Dict[str, Any]) -> JsonResponse:
    payload = {"ok": True}
    payload.update(data)
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})


def _json_err(e: Exception, status: int = 500) -> JsonResponse:
    traceback.print_exc()
    payload = {"ok": False, "error": repr(e)}
    return JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})


def _parse_date_ymd(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_json_body(request) -> Dict[str, Any]:
    ctype = (request.META.get("CONTENT_TYPE") or "").lower()
    if "application/json" in ctype:
        try:
            raw = request.body.decode("utf-8") if request.body else ""
            return json.loads(raw) if raw else {}
        except Exception:
            return {}
    return {}


def _to_float_or_none(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return None
    return float(s)


def _to_int_or_none(v):
    if v is None:
        return None
    if isinstance(v, int):
        return int(v)
    s = str(v).strip()
    if s == "":
        return None
    return int(s)


def _key_in(d: Dict[str, Any], *keys: str) -> bool:
    return any(k in d for k in keys)


def _field_exists(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _pick_field(model_cls, *candidates: str) -> Optional[str]:
    for name in candidates:
        if _field_exists(model_cls, name):
            return name
    return None


def _get_existing_db_columns(model_cls) -> set[str]:
    table = model_cls._meta.db_table
    connection = connections[REMOTE_DB]
    with connection.cursor() as cur:
        desc = connection.introspection.get_table_description(cur, table)
    return {c.name for c in desc}


def _get_existing_model_field_names(model_cls) -> set[str]:
    db_cols = _get_existing_db_columns(model_cls)
    names = set()
    for f in model_cls._meta.fields:
        if f.column in db_cols:
            names.add(f.name)
    return names


def _format_dt(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


def _norm_base_id(v: str):
    s = (v or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if len(s) >= 3:
        last_three = s[-3:]
        if last_three.isdigit():
            return int(last_three)
    return None


DEVICE_ID_F = "id"
DEVICE_NAME_F = _pick_field(Device, "name", "device_name")
DEVICE_CODE_F = _pick_field(Device, "device_code", "code", "device_code")
DEVICE_DESC_F = _pick_field(Device, "description")
DEVICE_NOTES_F = _pick_field(Device, "notes")
READ_TIME_F = _pick_field(DeviceReading, "reported_at", "collected_time", "collected_at", "created_at")


def _pick_existing_field(model_cls, *candidates: str) -> Optional[str]:
    existing_names = _get_existing_model_field_names(model_cls)
    for name in candidates:
        if name in existing_names:
            return name
    return None


def _get_reading_field_map() -> Dict[str, Optional[str]]:
    return {
        "time": _pick_existing_field(DeviceReading, "reported_at", "collected_time", "collected_at", "created_at"),
        "base_id": _pick_existing_field(DeviceReading, "pigsty_id", "base_id"),
        "image": _pick_existing_field(DeviceReading, "image_path", "image", "image_url", "photo"),

        "CO2": _pick_existing_field(DeviceReading, "co2", "CO2", "co2_ppm"),
        "temperature": _pick_existing_field(DeviceReading, "temperature", "temp"),
        "humidity": _pick_existing_field(DeviceReading, "humidity"),
        "C2H4": _pick_existing_field(DeviceReading, "c2h4", "C2H4"),
        "C2H5OH": _pick_existing_field(DeviceReading, "c2h5oh", "C2H5OH"),
        "CO": _pick_existing_field(DeviceReading, "co", "CO", "co_ppm"),
        "H2": _pick_existing_field(DeviceReading, "h2", "H2", "h2_ppm"),
        "O2": _pick_existing_field(DeviceReading, "o2", "O2"),
        "VOC": _pick_existing_field(DeviceReading, "voc", "VOC"),
    }


def _reading_get(obj: DeviceReading, field_name: Optional[str], default=None):
    if not field_name:
        return default
    return getattr(obj, field_name, default)


def _format_scalar(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if v is None:
        return None

    try:
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return v
        if hasattr(v, "as_tuple"):
            return float(v)
    except Exception:
        pass

    return v


def _build_media_url(request, raw) -> Optional[str]:
    if raw in (None, ""):
        return None

    if hasattr(raw, "url"):
        try:
            url = str(raw.url).strip()
            if not url:
                return None
            if url.startswith("http://") or url.startswith("https://"):
                return url
            return MEDIA_BASE_URL + url.lstrip("/")
        except Exception:
            text = str(raw).strip()
            if not text:
                return None
            if text.startswith("http://") or text.startswith("https://"):
                return text
            return MEDIA_BASE_URL + text.lstrip("/")

    text = str(raw).strip()
    if not text:
        return None

    if text.startswith("http://") or text.startswith("https://"):
        return text

    return MEDIA_BASE_URL + text.lstrip("/")


def _serialize_reading(request, obj: DeviceReading, field_map: Optional[Dict[str, Optional[str]]] = None) -> Dict[str, Any]:
    fm = field_map or _get_reading_field_map()

    return {
        "id": obj.pk,
        "CO2": _format_scalar(_reading_get(obj, fm["CO2"])),
        "temperature": _format_scalar(_reading_get(obj, fm["temperature"])),
        "humidity": _format_scalar(_reading_get(obj, fm["humidity"])),
        "collected_time": _format_scalar(_reading_get(obj, fm["time"])),
        "image": _build_media_url(request, _reading_get(obj, fm["image"])),
        "C2H4": _format_scalar(_reading_get(obj, fm["C2H4"])),
        "C2H5OH": _format_scalar(_reading_get(obj, fm["C2H5OH"])),
        "CO": _format_scalar(_reading_get(obj, fm["CO"])),
        "H2": _format_scalar(_reading_get(obj, fm["H2"])),
        "O2": _format_scalar(_reading_get(obj, fm["O2"])),
        "VOC": _format_scalar(_reading_get(obj, fm["VOC"])),
    }


def _parse_datetime_or_none(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None

    dt = parse_datetime(s)
    if dt is not None:
        return dt

    try:
        if len(s) == 16 and "T" in s:
            return datetime.fromisoformat(s + ":00")
        return datetime.fromisoformat(s)
    except Exception:
        raise ValueError(f"collected_time 格式无效：{s}")


def _build_device_q(dev_id, dev_name: str, dev_code: str) -> Optional[Q]:
    if dev_id not in (None, "", 0):
        try:
            return Q(pk=int(dev_id))
        except Exception:
            raise ValueError("id 必须是整数")
    if dev_name and DEVICE_NAME_F:
        return Q(**{DEVICE_NAME_F: dev_name})
    if dev_code and DEVICE_CODE_F:
        return Q(**{DEVICE_CODE_F: dev_code})
    return None


def _annotate_device_last_seen_and_base(qs):
    if not READ_TIME_F:
        return qs

    last_seen_sq = (
        DeviceReading.objects.using(REMOTE_DB)
        .filter(device_id=OuterRef("pk"))
        .values("device_id")
        .annotate(mx=Max(READ_TIME_F))
        .values("mx")[:1]
    )

    base_sq = (
        DeviceReading.objects.using(REMOTE_DB)
        .filter(device_id=OuterRef("pk"))
        .order_by(f"-{READ_TIME_F}")
        .values("pigsty_id")[:1]
    )

    image_sq = (
        DeviceReading.objects.using(REMOTE_DB)
        .filter(device_id=OuterRef("pk"))
        .order_by(f"-{READ_TIME_F}")
        .values("image_path")[:1]
    )

    return qs.annotate(
        last_seen_ts=Subquery(last_seen_sq),
        base_src_id=Subquery(base_sq),
        last_image_path=Subquery(image_sq),
    )


def _serialize_device(obj: Device, base_name_map: Dict[str, str] | None = None) -> Dict[str, Any]:
    name = getattr(obj, DEVICE_NAME_F, None) if DEVICE_NAME_F else None
    code = getattr(obj, DEVICE_CODE_F, None) if DEVICE_CODE_F else None
    desc = getattr(obj, DEVICE_DESC_F, None) if DEVICE_DESC_F else None

    collect_interval = getattr(obj, "collect_interval", None)
    created_at = getattr(obj, "created_at", None)
    updated_at = getattr(obj, "updated_at", None)

    last_seen = getattr(obj, "last_seen_ts", None)
    base_id = getattr(obj, "base_src_id", None)
    last_image_path = getattr(obj, "last_image_path", None)

    report_ts = last_seen or updated_at
    base_id_str = None if base_id is None else str(base_id)
    base_name = base_name_map.get(base_id_str) if (base_name_map and base_id_str) else None

    return {
        "id": obj.pk,
        "name": name,
        "device_code": code,
        "description": desc,
        "collect_interval": collect_interval,
        "created_at": _format_dt(created_at),
        "updated_at": _format_dt(report_ts),
        "device_updated_at": _format_dt(updated_at),

        "device_name": name,
        "code": code,
        "last_seen": _format_dt(last_seen),
        "base_id": base_id_str,
        "base_name": base_name,
        "image_path": last_image_path,
    }


@require_GET
def device_names(request):
    try:
        base_id = _norm_base_id(request.GET.get("base_id") or "")

        qs = Device.objects.using(REMOTE_DB).all()

        if base_id is not None:
            dev_ids = (
                DeviceReading.objects.using(REMOTE_DB)
                .filter(pigsty_id=base_id)
                .values_list("device_id", flat=True)
                .distinct()
            )
            qs = qs.filter(id__in=dev_ids)

        rows = list(
            qs.only("id", "name", "device_code")
              .values("id", "name", "device_code")
              .order_by("name", "id")
        )

        return _json_ok({
            "base_id": base_id,
            "devices": rows,
            "device_names": [r["name"] for r in rows if r.get("name")],
        })
    except Exception as e:
        return _json_err(e)


@require_GET
def stats(request):
    try:
        try:
            online_minutes = int(request.GET.get("online_minutes") or 10)
        except Exception:
            online_minutes = 10
        online_minutes = max(1, min(online_minutes, 24 * 60))

        total = Device.objects.using(REMOTE_DB).count()
        qs = _annotate_device_last_seen_and_base(Device.objects.using(REMOTE_DB).all())

        th = datetime.now() - timedelta(minutes=online_minutes)
        online = qs.filter(last_seen_ts__gte=th).count()
        offline = int(total) - int(online)

        return _json_ok({
            "kpi": {
                "total": int(total),
                "online": int(online),
                "offline": int(offline),
                "alarm": 0,
            },
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": f"online/offline 按 last_seen >= now-{online_minutes}min 推断（device 表无 status 字段）",
        })
    except Exception as e:
        return _json_err(e)


@require_GET
def dashboard_devices(request):
    try:
        try:
            page = max(int(request.GET.get("page", "1")), 1)
            page_size = min(max(int(request.GET.get("page_size", "10")), 1), 100)
        except Exception:
            page, page_size = 1, 10

        device_code = (request.GET.get("device_code") or "").strip()
        keyword = (request.GET.get("keyword") or "").strip()
        date_from = _parse_date_ymd(request.GET.get("date_from") or "")
        date_to = _parse_date_ymd(request.GET.get("date_to") or "")
        base_id = _norm_base_id(request.GET.get("base_id") or "")

        qs = Device.objects.using(REMOTE_DB).all().only(
            "id", "name", "device_code", "description", "collect_interval", "created_at", "updated_at"
        )

        if device_code and DEVICE_CODE_F:
            qs = qs.filter(**{f"{DEVICE_CODE_F}": device_code})

        if keyword:
            q_kw = Q()
            if DEVICE_NAME_F:
                q_kw |= Q(**{f"{DEVICE_NAME_F}__icontains": keyword})
            if DEVICE_CODE_F:
                q_kw |= Q(**{f"{DEVICE_CODE_F}__icontains": keyword})
            if DEVICE_DESC_F:
                q_kw |= Q(**{f"{DEVICE_DESC_F}__icontains": keyword})
            qs = qs.filter(q_kw)

        qs = _annotate_device_last_seen_and_base(qs)

        if base_id is not None:
            qs = qs.filter(base_src_id=base_id)

        if date_from:
            qs = qs.filter(
                Q(last_seen_ts__date__gte=date_from) |
                Q(last_seen_ts__isnull=True, updated_at__date__gte=date_from)
            )
        if date_to:
            qs = qs.filter(
                Q(last_seen_ts__date__lte=date_to) |
                Q(last_seen_ts__isnull=True, updated_at__date__lte=date_to)
            )

        qs = qs.order_by("-id")
        total = qs.count()

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)

        items = []
        for obj in page_obj.object_list:
            last_seen = getattr(obj, "last_seen_ts", None)
            report_ts = last_seen or getattr(obj, "updated_at", None)

            items.append({
                "id": obj.pk,
                "name": getattr(obj, "name", None),
                "device_code": getattr(obj, "device_code", None),
                "description": getattr(obj, "description", None),
                "collect_interval": getattr(obj, "collect_interval", None),
                "created_at": _format_dt(getattr(obj, "created_at", None)),
                "updated_at": _format_dt(report_ts),

                "device_name": getattr(obj, "name", None),
                "code": getattr(obj, "device_code", None),
                "last_seen": _format_dt(last_seen),
                "base_id": None if getattr(obj, "base_src_id", None) is None else str(getattr(obj, "base_src_id")),
                "image_path": getattr(obj, "last_image_path", None),
            })

        return _json_ok({
            "base_id": base_id,
            "items": items,
            "total": int(total),
        })
    except Exception as e:
        return _json_err(e)


@require_GET
def trend(request):
    device_id_raw = (request.GET.get("device_id") or request.GET.get("id") or "").strip()
    device_name = (request.GET.get("device_name") or request.GET.get("name") or "").strip()
    device_code = (request.GET.get("device_code") or request.GET.get("code") or "").strip()
    base_id = _norm_base_id(request.GET.get("base_id") or "")

    range_ = (request.GET.get("range") or "7d").strip().lower()
    days = 7 if range_ == "7d" else 30

    try:
        limit = int(request.GET.get("limit") or 800)
    except Exception:
        limit = 800
    limit = max(50, min(limit, 2000))

    try:
        time_f = _pick_field(DeviceReading, "reported_at", "collected_time", "collected_at", "created_at")
        if not time_f:
            return _json_ok({"x": [], "series": [], "note": "找不到时间字段"})

        existing_fields = _get_existing_model_field_names(DeviceReading)
        if time_f not in existing_fields:
            return _json_ok({"x": [], "series": [], "note": f"时间字段 {time_f} 不存在于真实表"})

        numeric_types = (
            models.IntegerField, models.BigIntegerField, models.SmallIntegerField,
            models.PositiveIntegerField, models.PositiveSmallIntegerField,
            models.FloatField, models.DecimalField,
        )
        series_cols: List[str] = []
        excluded = {"id", time_f, "device_name", "image_path"}
        for f in DeviceReading._meta.fields:
            if f.name in excluded:
                continue
            if f.name not in existing_fields:
                continue
            if isinstance(f, numeric_types):
                series_cols.append(f.name)

        if not series_cols:
            return _json_ok({"x": [], "series": [], "note": "没有可绘制数值列"})

        resolved_id: Optional[int] = None

        if device_id_raw:
            try:
                resolved_id = int(device_id_raw)
            except Exception:
                return _json_err(ValueError("device_id/id 必须是整数"), status=400)

        if resolved_id is None and device_code and DEVICE_CODE_F:
            dev = Device.objects.using(REMOTE_DB).filter(**{DEVICE_CODE_F: device_code}).only("id").first()
            if dev:
                resolved_id = int(dev.id)

        if resolved_id is None and device_name and DEVICE_NAME_F:
            dev = Device.objects.using(REMOTE_DB).filter(**{DEVICE_NAME_F: device_name}).only("id").order_by("id").first()
            if dev:
                resolved_id = int(dev.id)

        if resolved_id is None:
            return _json_ok({"x": [], "series": [], "note": "缺少 device_id（也可传 id / device_name / device_code）"})

        qs = DeviceReading.objects.using(REMOTE_DB).filter(device_id=resolved_id)

        if base_id is not None:
            qs = qs.filter(pigsty_id=base_id)

        max_t = qs.aggregate(mx=Max(time_f)).get("mx")
        if not max_t:
            return _json_ok({
                "x": [],
                "series": [],
                "note": f"device_id={resolved_id} 在 environment_data 中没有数据（base_id={base_id}）",
                "device_id": resolved_id,
                "base_id": base_id,
            })

        start_t = max_t - timedelta(days=days)
        qs = qs.filter(**{f"{time_f}__gte": start_t})

        value_fields = [time_f] + series_cols
        rows = list(qs.order_by(f"-{time_f}").values(*value_fields)[:limit])
        rows.reverse()

        x = []
        for r in rows:
            t = r.get(time_f)
            x.append(t.strftime("%Y-%m-%d %H:%M:%S") if isinstance(t, datetime) else str(t or ""))

        series = [{"name": col, "data": [rr.get(col) for rr in rows]} for col in series_cols]
        return _json_ok({
            "x": x,
            "series": series,
            "device_id": resolved_id,
            "base_id": base_id,
        })

    except Exception as e:
        return _json_err(e)


@require_GET
def device_readings_list(request, device_id: int):
    try:
        dev = Device.objects.using(REMOTE_DB).filter(pk=device_id).only("id").first()
        if not dev:
            return _json_err(RuntimeError("设备不存在"), status=404)

        try:
            page = max(int(request.GET.get("page", "1")), 1)
            page_size = min(max(int(request.GET.get("page_size", "10")), 1), 100)
        except Exception:
            page, page_size = 1, 10

        keyword = (request.GET.get("keyword") or "").strip()
        date_from = _parse_date_ymd(request.GET.get("date_from") or "")
        date_to = _parse_date_ymd(request.GET.get("date_to") or "")
        base_id = _norm_base_id(request.GET.get("base_id") or "")

        sort_by = (request.GET.get("sort_by") or "collected_time").strip()
        sort_dir = (request.GET.get("sort_dir") or "desc").strip().lower()
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"

        fm = _get_reading_field_map()
        time_f = fm["time"]
        base_f = fm["base_id"]
        image_f = fm["image"]

        qs = DeviceReading.objects.using(REMOTE_DB).filter(device_id=device_id)

        if base_id is not None and base_f:
            qs = qs.filter(**{base_f: base_id})

        if time_f:
            if date_from:
                qs = qs.filter(**{f"{time_f}__date__gte": date_from})
            if date_to:
                qs = qs.filter(**{f"{time_f}__date__lte": date_to})

        if keyword:
            q_kw = Q()

            if image_f:
                q_kw |= Q(**{f"{image_f}__icontains": keyword})

            if time_f:
                kw_date = _parse_date_ymd(keyword)
                if kw_date:
                    q_kw |= Q(**{f"{time_f}__date": kw_date})

            num = None
            try:
                num = float(keyword)
            except Exception:
                num = None

            if num is not None:
                for k in ["CO2", "temperature", "humidity", "C2H4", "C2H5OH", "CO", "H2", "O2", "VOC"]:
                    f = fm.get(k)
                    if f:
                        q_kw |= Q(**{f: num})

            if q_kw.children:
                qs = qs.filter(q_kw)

        sort_field_map = {
            "id": "id",
            "CO2": fm.get("CO2"),
            "temperature": fm.get("temperature"),
            "humidity": fm.get("humidity"),
            "collected_time": fm.get("time"),
            "C2H4": fm.get("C2H4"),
            "C2H5OH": fm.get("C2H5OH"),
            "CO": fm.get("CO"),
            "H2": fm.get("H2"),
            "O2": fm.get("O2"),
            "VOC": fm.get("VOC"),
        }

        actual_sort_field = sort_field_map.get(sort_by)

        if actual_sort_field:
            prefix = "" if sort_dir == "asc" else "-"
            if actual_sort_field == "id":
                qs = qs.order_by(f"{prefix}id")
            else:
                qs = qs.order_by(f"{prefix}{actual_sort_field}", "-id")
        else:
            if time_f:
                qs = qs.order_by(f"-{time_f}", "-id")
            else:
                qs = qs.order_by("-id")

        total = qs.count()

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)

        results = [_serialize_reading(request, obj, fm) for obj in page_obj.object_list]

        return _json_ok({
            "device_id": device_id,
            "base_id": base_id,
            "results": results,
            "total": int(total),
            "page": int(page),
            "page_size": int(page_size),
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        })
    except Exception as e:
        return _json_err(e)


@csrf_exempt
@require_POST
def update_reading(request, reading_id: int):
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    try:
        obj = DeviceReading.objects.using(REMOTE_DB).filter(pk=reading_id).first()
        if not obj:
            return _json_err(RuntimeError("读数记录不存在"), status=404)

        fm = _get_reading_field_map()
        update_fields: List[str] = []

        numeric_keys = ["CO2", "temperature", "humidity", "C2H4", "C2H5OH", "CO", "H2", "O2", "VOC"]
        for key in numeric_keys:
            if key in data:
                f = fm.get(key)
                if not f:
                    continue
                setattr(obj, f, _to_float_or_none(data.get(key)))
                update_fields.append(f)

        if "collected_time" in data:
            f = fm.get("time")
            if f:
                setattr(obj, f, _parse_datetime_or_none(data.get("collected_time")))
                update_fields.append(f)

        if "image" in data:
            f = fm.get("image")
            if f:
                raw = data.get("image")
                text = "" if raw is None else str(raw).strip()
                setattr(obj, f, text or None)
                update_fields.append(f)

        if not update_fields:
            return _json_err(ValueError("没有提供任何可更新字段"), status=400)

        update_fields = list(dict.fromkeys(update_fields))

        with transaction.atomic(using=REMOTE_DB):
            obj.save(using=REMOTE_DB, update_fields=update_fields)

        return _json_ok({
            "updated": 1,
            "reading": _serialize_reading(request, obj, fm),
        })
    except Exception as e:
        return _json_err(e)


@csrf_exempt
@require_POST
def delete_reading(request, reading_id: int):
    try:
        obj = DeviceReading.objects.using(REMOTE_DB).filter(pk=reading_id).first()
        if not obj:
            return _json_err(RuntimeError("读数记录不存在"), status=404)

        fm = _get_reading_field_map()
        row = _serialize_reading(request, obj, fm)

        obj.delete(using=REMOTE_DB)

        return _json_ok({
            "deleted": 1,
            "reading": row,
        })
    except Exception as e:
        return _json_err(e)


@csrf_exempt
@require_POST
def save_device_location(request):
    return _json_err(RuntimeError("当前 device 表无经纬度/位置信息字段，save_device_location 接口不支持"), status=400)


@csrf_exempt
@require_POST
def update_device(request):
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or data.get("name") or "").strip()
    dev_code = (data.get("device_code") or data.get("code") or "").strip()

    match_name = (data.get("match_device_name") or "").strip()
    match_code = (data.get("match_device_code") or "").strip()

    try:
        q = _build_device_q(dev_id, match_name or dev_name, match_code or dev_code)
        if q is None:
            return _json_err(ValueError("缺少定位字段：id 或 device_name/name 或 device_code/code"), status=400)

        obj = Device.objects.using(REMOTE_DB).filter(q).order_by("id").first()
        if not obj:
            return _json_err(RuntimeError("未更新：设备不存在或条件未命中"), status=404)

        update_fields: List[str] = []

        if _key_in(data, "device_name", "name") and DEVICE_NAME_F:
            text = "" if (data.get("device_name") is None and data.get("name") is None) else str(data.get("device_name") or data.get("name")).strip()
            field = obj._meta.get_field(DEVICE_NAME_F)
            if text == "":
                setattr(obj, DEVICE_NAME_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_NAME_F, text)
            update_fields.append(DEVICE_NAME_F)

        if _key_in(data, "device_code", "code") and DEVICE_CODE_F:
            text = "" if (data.get("device_code") is None and data.get("code") is None) else str(data.get("device_code") or data.get("code")).strip()
            field = obj._meta.get_field(DEVICE_CODE_F)
            if text == "":
                setattr(obj, DEVICE_CODE_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_CODE_F, text)
            update_fields.append(DEVICE_CODE_F)

        if _key_in(data, "description") and DEVICE_DESC_F:
            text = "" if data.get("description") is None else str(data.get("description")).strip()
            field = obj._meta.get_field(DEVICE_DESC_F)
            if text == "":
                setattr(obj, DEVICE_DESC_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_DESC_F, text)
            update_fields.append(DEVICE_DESC_F)

        if _key_in(data, "notes") and DEVICE_NOTES_F:
            text = "" if data.get("notes") is None else str(data.get("notes")).strip()
            field = obj._meta.get_field(DEVICE_NOTES_F)
            if text == "":
                setattr(obj, DEVICE_NOTES_F, None if field.null else "")
            else:
                setattr(obj, DEVICE_NOTES_F, text)
            update_fields.append(DEVICE_NOTES_F)

        float_map = {
            "collect_interval": "collect_interval",
            "extract_air_time": "extract_air_time",
            "extract_tested_gas_tin": "extract_tested_gas_tin",
            "extract_wait_time": "extract_wait_time",
        }
        for k, field_name in float_map.items():
            if _key_in(data, k) and _field_exists(Device, field_name):
                v = _to_float_or_none(data.get(k))
                setattr(obj, field_name, v)
                update_fields.append(field_name)

        if not update_fields:
            return _json_err(ValueError("没有提供任何可更新字段（新 device 表不支持 base/status/经纬度/location）"), status=400)

        update_fields = list(dict.fromkeys(update_fields))
        with transaction.atomic(using=REMOTE_DB):
            obj.save(update_fields=update_fields, using=REMOTE_DB)

        qs = _annotate_device_last_seen_and_base(Device.objects.using(REMOTE_DB).filter(pk=obj.pk))
        obj2 = qs.first() or obj

        return _json_ok({"updated": 1, "device": _serialize_device(obj2)})

    except Exception as e:
        return _json_err(e)


@csrf_exempt
@require_POST
def delete_device(request):
    body = _parse_json_body(request)
    data: Dict[str, Any] = {}
    data.update(request.POST.dict() if hasattr(request, "POST") else {})
    data.update(body or {})

    dev_id = data.get("id") or data.get("device_id")
    dev_name = (data.get("device_name") or data.get("name") or "").strip()
    dev_code = (data.get("device_code") or data.get("code") or "").strip()

    try:
        q = _build_device_q(dev_id, dev_name, dev_code)
        if q is None:
            return _json_err(ValueError("缺少定位字段：id 或 device_name/name 或 device_code/code"), status=400)

        qs = _annotate_device_last_seen_and_base(Device.objects.using(REMOTE_DB).filter(q).order_by("id"))
        obj = qs.first()
        if not obj:
            return _json_err(RuntimeError("未删除：设备不存在或条件未命中"), status=404)

        row = _serialize_device(obj)
        obj.delete(using=REMOTE_DB)

        return _json_ok({"deleted": 1, "device": row})

    except Exception as e:
        return _json_err(e)